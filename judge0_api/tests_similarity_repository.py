"""Opt-in integration checks against a migrated local Postgres database.

Set SIMILARITY_TEST_DATABASE_URL to a loopback Postgres URL before running this
file. Each test commits its own random fixture cohort and deletes only that
cohort afterwards; migrations and existing application records are untouched.
"""

import os
from uuid import uuid4

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from similarity_repository import PsycopgSimilarityRepository
from similarity_service import (
    ALGORITHM_VERSION,
    MatchNotFoundError,
    SimilarityService,
)


TEST_DATABASE_URL = os.getenv("SIMILARITY_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Set SIMILARITY_TEST_DATABASE_URL to opt in to local Postgres tests.",
)


@pytest.fixture(scope="module")
def database_url():
    settings = conninfo_to_dict(TEST_DATABASE_URL)
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    assert settings.get("host") in local_hosts, "Integration tests require a loopback host."
    assert settings.get("hostaddr", "127.0.0.1") in local_hosts
    assert "service" not in settings, "Use an explicit local Postgres URL."
    with psycopg.connect(TEST_DATABASE_URL, connect_timeout=5) as connection:
        columns = {
            row[0]
            for row in connection.execute(
                """select column_name from information_schema.columns
                   where table_schema = 'public' and table_name = 'similarity_scans'"""
            )
        }
    assert {"compared_pair_count", "skipped_pair_count", "metadata"} <= columns, (
        "Local similarity schema is outdated. Apply "
        "20260905020000_preserve_similarity_evidence.sql before opting in."
    )
    return TEST_DATABASE_URL


class LocalCohort:
    def __init__(self, database_url):
        self.database_url = database_url
        self.repository = PsycopgSimilarityRepository(database_url)
        self.service = SimilarityService(self.repository)
        self.marker = f"similarity-test-{uuid4()}"
        self.assessments = [uuid4(), uuid4()]
        self.questions = [uuid4(), uuid4()]
        self.sections = [uuid4(), uuid4()]
        self.students = [uuid4() for _ in range(6)]
        self.answers = []

    def connect(self):
        return psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            connect_timeout=5,
            options="-c statement_timeout=15000",
        )

    def create(self):
        with self.connect() as connection:
            for index, question in enumerate(self.questions):
                connection.execute(
                    """insert into public.questions
                       (id, question_name, question_text, model_answer)
                       values (%s, %s, 'Integration fixture', 'int model(void){return 0;}')""",
                    (question, f"{self.marker}-question-{index}"),
                )
            for index, section in enumerate(self.sections):
                connection.execute(
                    "insert into public.block_sections (id, name) values (%s, %s)",
                    (section, f"{self.marker}-block-{index}"),
                )
            for index, student in enumerate(self.students):
                connection.execute(
                    """insert into public.students (id, student_number, display_name)
                       values (%s, %s, %s)""",
                    (student, f"{self.marker}-{index}", f"Fixture student {index}"),
                )
            for index, assessment in enumerate(self.assessments):
                connection.execute(
                    """insert into public.assessments (id, name, status)
                       values (%s, %s, 'active')""",
                    (assessment, f"{self.marker}-assessment-{index}"),
                )
                for question in self.questions:
                    connection.execute(
                        """insert into public.assessment_questions (assessment_id, question_id)
                           values (%s, %s)""",
                        (assessment, question),
                    )
                for student_index, student in enumerate(self.students):
                    connection.execute(
                        """insert into public.assessment_roster
                           (assessment_id, student_id, block_section_id) values (%s, %s, %s)""",
                        (assessment, student, self.sections[student_index % 2]),
                    )

    def add_answer(self, student=0, *, assessment=0, question=0, status="verified",
                   current=True, code="int add(int a, int b) { return a+b; }"):
        submission_id = uuid4()
        with self.connect() as connection:
            row = connection.execute(
                """insert into public.submissions
                   (id, image_url, assessment_id, question_id, student_id,
                    block_section_id, status, is_current, verified_text, extracted_text)
                   values (%s, 'https://example.invalid/fixture.png', %s, %s, %s,
                           %s, %s, %s, %s, 'RAW OCR MUST NOT BE COMPARED')
                   returning id, verified_version""",
                (submission_id, self.assessments[assessment], self.questions[question],
                 self.students[student], self.sections[student % 2], status, current, code),
            ).fetchone()
        self.answers.append(submission_id)
        assert row["verified_version"] == (1 if code is not None else 0)
        return str(submission_id)

    def set_code(self, submission_id, code):
        with self.connect() as connection:
            return connection.execute(
                """update public.submissions set verified_text = %s
                   where id = %s returning verified_version""",
                (code, submission_id),
            ).fetchone()["verified_version"]

    def set_starter(self, starter):
        with self.connect() as connection:
            connection.execute(
                """update public.assessment_questions set starter_code = %s
                   where assessment_id = %s and question_id = %s""",
                (starter, self.assessments[0], self.questions[0]),
            )

    def clean(self):
        with self.connect() as connection:
            connection.execute(
                "delete from public.submissions where assessment_id = any(%s)",
                (self.assessments,),
            )
            connection.execute(
                "delete from public.assessments where id = any(%s)", (self.assessments,),
            )
            connection.execute(
                "delete from public.questions where id = any(%s)", (self.questions,),
            )
            connection.execute(
                "delete from public.students where id = any(%s)", (self.students,),
            )
            connection.execute(
                "delete from public.block_sections where id = any(%s)", (self.sections,),
            )


@pytest.fixture
def cohort(database_url):
    fixture = LocalCohort(database_url)
    fixture.create()
    try:
        yield fixture
    finally:
        fixture.clean()


def test_group_inputs_include_cross_section_verified_answers_and_exclude_other_scopes(cohort):
    first = cohort.add_answer(0)
    second = cohort.add_answer(1, status="graded")
    historical = cohort.add_answer(0, current=False)
    cohort.add_answer(2, status="pending")
    other_assessment = cohort.add_answer(0, assessment=1)
    cohort.add_answer(3, question=1)

    rows = cohort.repository.get_group_inputs(
        str(cohort.assessments[0]), str(cohort.questions[0]),
    )

    assert {str(row["id"]) for row in rows} == {first, second}
    assert {row["block_section_id"] for row in rows} == set(cohort.sections)
    assert all("RAW OCR" not in row["verified_text"] for row in rows)
    assert cohort.repository.get_submission_scope(historical) is None
    scan = cohort.service.scan_submission(first)
    assert {match["peer_submission_id"] for match in scan["matches"]} == {second}
    assert cohort.service.get_submission_summary(other_assessment)["status"] == "not_checked"
    with pytest.raises(MatchNotFoundError):
        cohort.service.get_match_detail(first, other_assessment)


def test_scan_round_trips_counts_labels_classification_and_independent_ranges(cohort):
    starter = "int helper(void) { return 7; }"
    before = "int before(void) { return 1; }"
    after = "int after(void) { return 2; }"
    cohort.set_starter(starter)
    first = cohort.add_answer(0, code=starter + before + after)
    second = cohort.add_answer(1, code=before + starter + after)
    cohort.add_answer(2, code=None)

    scanned = cohort.service.scan_submission(first)
    reopened = cohort.service.get_submission_summary(first)
    peer_summary = cohort.service.get_submission_summary(second)
    stored = cohort.repository.get_latest_scan(
        str(cohort.assessments[0]), str(cohort.questions[0]),
    )

    assert reopened["status"] == "complete"
    assert reopened["eligible_submission_count"] == 2
    assert reopened["compared_pair_count"] == 1
    assert reopened["skipped_pair_count"] == 2
    assert reopened["skipped_reasons"]["missing_code"] == 2
    assert reopened["matches"] == scanned["matches"]
    assert reopened["matches"][0]["match_type"] == "normalized_duplicate"
    assert reopened["matches"][0]["peer_student_name"] == "Fixture student 1"
    assert reopened["matches"][0]["peer_block_section_name"] == f"{cohort.marker}-block-1"
    assert peer_summary["matches"][0]["peer_submission_id"] == first
    assert stored["metadata"]["skipped_reasons"] == reopened["skipped_reasons"]
    assert stored["completed_at"] is not None
    match = stored["matches"][0]
    assert str(match["lower_submission_id"]) < str(match["higher_submission_id"])
    assert match["lower_verified_version"] == match["higher_verified_version"] == 1

    detail = cohort.service.get_match_detail(first, second)
    assert detail["submission_code"] == starter + before + after
    assert detail["peer_code"] == before + starter + after
    assert len(detail["submission_ranges"]) == 1
    assert len(detail["peer_ranges"]) == 2
    assert detail["submission_coverage"] == detail["peer_coverage"] == 1.0


def test_verified_edit_invalidates_both_summaries_and_rejects_stored_detail(cohort):
    first = cohort.add_answer(0)
    second = cohort.add_answer(1)
    scan = cohort.service.scan_submission(first)
    lower, higher = sorted((first, second))
    assert cohort.repository.get_match_detail(scan["scan_id"], lower, higher) is not None

    assert cohort.set_code(second, "int changed(void) { return 99; }") == 2

    assert cohort.service.get_submission_summary(first)["status"] == "outdated"
    assert cohort.service.get_submission_summary(second)["status"] == "outdated"
    assert cohort.repository.get_match_detail(scan["scan_id"], lower, higher) is None
    with pytest.raises(MatchNotFoundError):
        cohort.service.get_match_detail(first, second)


def test_starter_revision_invalidates_persisted_matches_without_a_code_edit(cohort):
    first = cohort.add_answer(0)
    second = cohort.add_answer(1)
    cohort.service.scan_submission(first)

    cohort.set_starter("int supplied(void) { return 42; }")

    assert cohort.service.get_submission_summary(first)["status"] == "outdated"
    assert cohort.service.get_submission_summary(second)["status"] == "outdated"
    with pytest.raises(MatchNotFoundError):
        cohort.service.get_match_detail(first, second)


def test_newer_checking_scan_prevents_reading_older_complete_detail(cohort):
    first = cohort.add_answer(0)
    second = cohort.add_answer(1)
    old = cohort.service.scan_submission(first)
    newer = cohort.repository.create_checking_scan(
        str(cohort.assessments[0]), str(cohort.questions[0]), ALGORITHM_VERSION, "new-attempt",
    )

    assert str(newer["id"]) != old["scan_id"]
    lower, higher = sorted((first, second))
    assert cohort.repository.get_match_detail(old["scan_id"], lower, higher) is None


def test_match_inserts_and_complete_transition_roll_back_together(cohort):
    first = cohort.add_answer(0)
    second = cohort.add_answer(1)
    scan = cohort.repository.create_checking_scan(
        str(cohort.assessments[0]), str(cohort.questions[0]), ALGORITHM_VERSION, "fixture",
    )
    lower, higher = sorted((first, second))
    match = {
        "lower_submission_id": lower,
        "higher_submission_id": higher,
        "lower_verified_version": 1,
        "higher_verified_version": 1,
        "match_type": "exact_duplicate",
        "matched_token_count": 12,
        "lower_coverage": 1.0,
        "higher_coverage": 1.0,
        "source_ranges": {"left": [], "right": []},
    }

    with pytest.raises(psycopg.IntegrityError):
        cohort.repository.complete_scan(str(scan["id"]), [match, match], 1, 0, "fixture")

    stored = cohort.repository.get_latest_scan(
        str(cohort.assessments[0]), str(cohort.questions[0]),
    )
    assert stored["status"] == "checking"
    assert stored["matches"] == []
    cohort.repository.fail_scan(str(scan["id"]), "Fixture transaction failure")
    stored = cohort.repository.get_latest_scan(
        str(cohort.assessments[0]), str(cohort.questions[0]),
    )
    assert stored["status"] == "failed"
    assert stored["error_message"] == "Fixture transaction failure"
