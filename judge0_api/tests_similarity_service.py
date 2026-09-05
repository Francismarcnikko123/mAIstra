from datetime import datetime, timedelta, timezone

import pytest

from similarity_service import (
    ALGORITHM_VERSION,
    MissingComparisonMetadataError,
    SimilarityService,
    compute_cohort_fingerprint,
)


COMPLETE_MATCH = {
    "match_type": "similar_code",
    "review_recommended": True,
    "matched_token_count": 20,
    "left_coverage": 0.8,
    "right_coverage": 0.7,
    "left_ranges": [{"start": {"row": 0, "column": 0}, "end": {"row": 2, "column": 1}}],
    "right_ranges": [{"start": {"row": 1, "column": 0}, "end": {"row": 3, "column": 1}}],
    "analysis_state": "complete",
}


class FakeRepository:
    def __init__(self):
        self.scope = {
            "id": "submission-a",
            "assessment_id": "assessment-1",
            "question_id": "question-1",
            "student_id": "student-1",
            "block_section_id": "section-a",
        }
        self.group_inputs = [
            {
                "id": "submission-a",
                "student_id": "student-1",
                "block_section_id": "section-a",
                "verified_text": "code-a",
                "verified_version": 1,
                "student_name": "Ana",
                "block_section_name": "A",
            },
            {
                "id": "submission-b",
                "student_id": "student-2",
                "block_section_id": "section-b",
                "verified_text": "code-b",
                "verified_version": 2,
                "student_name": "Ben",
                "block_section_name": "B",
            },
        ]
        self.starter_code = "starter"
        self.latest_scan = None
        self.completed = None
        self.failed = None

    def get_submission_scope(self, submission_id):
        return self.scope

    def get_group_inputs(self, assessment_id, question_id):
        return list(self.group_inputs)

    def get_starter_code(self, assessment_id, question_id):
        return self.starter_code

    def create_checking_scan(
        self,
        assessment_id,
        question_id,
        algorithm_version,
        cohort_fingerprint,
    ):
        return {
            "id": "scan-1",
            "status": "checking",
            "assessment_id": assessment_id,
            "question_id": question_id,
            "algorithm_version": algorithm_version,
            "cohort_fingerprint": cohort_fingerprint,
            "started_at": datetime.now(timezone.utc),
            "matches": [],
        }

    def complete_scan(
        self,
        scan_id,
        matches,
        compared_count,
        skipped_count,
        cohort_fingerprint,
        metadata=None,
    ):
        self.completed = {
            "scan_id": scan_id,
            "matches": matches,
            "compared_count": compared_count,
            "skipped_count": skipped_count,
            "cohort_fingerprint": cohort_fingerprint,
            "metadata": metadata,
        }

    def fail_scan(self, scan_id, message):
        self.failed = {"scan_id": scan_id, "message": message}

    def get_latest_scan(self, assessment_id, question_id):
        return self.latest_scan

    def get_match_detail(
        self,
        scan_id,
        lower_submission_id,
        higher_submission_id,
    ):
        return None


def test_scan_rejects_missing_comparison_metadata():
    repository = FakeRepository()
    repository.scope["assessment_id"] = None
    service = SimilarityService(repository)

    with pytest.raises(MissingComparisonMetadataError):
        service.scan_submission("submission-a")


def test_scan_compares_cross_section_students_once_and_skips_same_student():
    repository = FakeRepository()
    repository.group_inputs.extend(
        [
            {
                "id": "submission-c",
                "student_id": "student-1",
                "block_section_id": "section-b",
                "verified_text": "code-c",
                "verified_version": 1,
                "student_name": "Ana",
                "block_section_name": "B",
            },
            {
                "id": "submission-d",
                "student_id": "student-4",
                "block_section_id": "section-a",
                "verified_text": None,
                "verified_version": 0,
                "student_name": "Dan",
                "block_section_name": "A",
            },
        ]
    )
    compared_pairs = []

    def compare(left, right):
        compared_pairs.append((left, right))
        return COMPLETE_MATCH

    service = SimilarityService(
        repository,
        prepare=lambda code, starter: code,
        compare=compare,
    )

    result = service.scan_submission("submission-a")

    assert result["status"] == "complete"
    assert compared_pairs == [
        ("code-a", "code-b"),
        ("code-b", "code-c"),
    ]
    assert repository.completed["compared_count"] == 2
    assert repository.completed["skipped_count"] == 4
    assert {
        (match["lower_submission_id"], match["higher_submission_id"])
        for match in repository.completed["matches"]
    } == {
        ("submission-a", "submission-b"),
        ("submission-b", "submission-c"),
    }


def test_scan_saves_a_complete_empty_result():
    repository = FakeRepository()
    service = SimilarityService(
        repository,
        prepare=lambda code, starter: code,
        compare=lambda left, right: {
            **COMPLETE_MATCH,
            "match_type": "no_match",
            "review_recommended": False,
            "matched_token_count": 0,
        },
    )

    result = service.scan_submission("submission-a")

    assert result["status"] == "complete"
    assert result["match_count"] == 0
    assert repository.completed["matches"] == []


def test_cohort_fingerprint_is_stable_for_reordered_inputs():
    repository = FakeRepository()
    reversed_inputs = list(reversed(repository.group_inputs))
    original = compute_cohort_fingerprint(repository.group_inputs, "starter")

    assert original == compute_cohort_fingerprint(reversed_inputs, "starter")
    assert original != compute_cohort_fingerprint(reversed_inputs, "changed")
    reversed_inputs[0]["verified_version"] = 99
    assert original != compute_cohort_fingerprint(reversed_inputs, "starter")
    assert ALGORITHM_VERSION == "c-tree-sitter-winnowing-v2"


def test_scan_is_marked_outdated_if_the_cohort_changes_during_analysis():
    class ChangingRepository(FakeRepository):
        def __init__(self):
            super().__init__()
            self.read_count = 0

        def get_group_inputs(self, assessment_id, question_id):
            self.read_count += 1
            rows = super().get_group_inputs(assessment_id, question_id)
            if self.read_count > 1:
                rows[0] = {**rows[0], "verified_version": 2}
            return rows

    repository = ChangingRepository()
    service = SimilarityService(
        repository,
        prepare=lambda code, starter: code,
        compare=lambda left, right: COMPLETE_MATCH,
    )

    result = service.scan_submission("submission-a")

    assert result["status"] == "outdated"
    assert repository.completed is None
    assert repository.failed["scan_id"] == "scan-1"


def test_complete_scan_is_outdated_when_verified_versions_change():
    repository = FakeRepository()
    repository.latest_scan = {
        "id": "scan-old",
        "status": "complete",
        "cohort_fingerprint": "old-fingerprint",
        "compared_submission_count": 1,
        "skipped_submission_count": 0,
        "matches": [],
    }
    service = SimilarityService(repository)

    result = service.get_submission_summary("submission-a")

    assert result["status"] == "outdated"


def test_stale_checking_scan_is_unavailable():
    repository = FakeRepository()
    repository.latest_scan = {
        "id": "scan-stale",
        "status": "checking",
        "cohort_fingerprint": compute_cohort_fingerprint(
            repository.group_inputs,
            repository.starter_code,
        ),
        "started_at": datetime.now(timezone.utc) - timedelta(minutes=20),
        "matches": [],
    }
    service = SimilarityService(repository)

    result = service.get_submission_summary("submission-a")

    assert result["status"] == "unavailable"
    assert "timed out" in result["error"].lower()


def test_scan_failure_is_persisted_without_exposing_internal_details():
    repository = FakeRepository()
    service = SimilarityService(
        repository,
        prepare=lambda code, starter: code,
        compare=lambda left, right: (_ for _ in ()).throw(RuntimeError("broken")),
    )

    with pytest.raises(RuntimeError, match="broken"):
        service.scan_submission("submission-a")

    assert repository.failed == {
        "scan_id": "scan-1",
        "message": "Similarity analysis failed.",
    }


def test_exact_duplicate_evidence_survives_parse_errors():
    repository = FakeRepository()
    for row in repository.group_inputs:
        row['verified_text'] = 'int main(void) { int total ='
    result = SimilarityService(repository).scan_submission('submission-a')
    assert result['matches'][0]['match_type'] == 'exact_duplicate'
    assert result['skipped_reasons']['partial_analysis'] == 1


def test_persistence_retains_classification_and_unequal_range_lists():
    repository = FakeRepository()
    evidence = {**COMPLETE_MATCH, 'match_type': 'normalized_duplicate',
                'right_ranges': COMPLETE_MATCH['right_ranges'] * 2}
    SimilarityService(repository, prepare=lambda code, starter: code,
                      compare=lambda left, right: evidence).scan_submission('submission-a')
    match = repository.completed['matches'][0]
    assert match['match_type'] == 'normalized_duplicate'
    assert len(match['source_ranges']['right']) == 2


def test_identity_reassignment_invalidates_existing_findings():
    repository = FakeRepository()
    original = compute_cohort_fingerprint(repository.group_inputs, '')
    repository.group_inputs[0]['student_id'] = 'student-2'
    assert compute_cohort_fingerprint(repository.group_inputs, '') != original
