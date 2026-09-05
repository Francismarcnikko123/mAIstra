from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except ImportError:  # The API reports a configuration error until dependencies exist.
    psycopg = None
    dict_row = None
    Jsonb = None


class SimilarityRepository(Protocol):
    def get_submission_scope(
        self,
        submission_id: str,
    ) -> Mapping[str, Any] | None: ...

    def get_group_inputs(
        self,
        assessment_id: str,
        question_id: str,
    ) -> list[Mapping[str, Any]]: ...

    def get_starter_code(self, assessment_id: str, question_id: str) -> str: ...

    def create_checking_scan(
        self,
        assessment_id: str,
        question_id: str,
        algorithm_version: str,
        cohort_fingerprint: str,
    ) -> Mapping[str, Any]: ...

    def complete_scan(
        self,
        scan_id: str,
        matches: Sequence[Mapping[str, Any]],
        compared_count: int,
        skipped_count: int,
        cohort_fingerprint: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None: ...

    def fail_scan(self, scan_id: str, message: str) -> None: ...

    def get_latest_scan(
        self,
        assessment_id: str,
        question_id: str,
    ) -> Mapping[str, Any] | None: ...

    def get_match_detail(
        self,
        scan_id: str,
        lower_submission_id: str,
        higher_submission_id: str,
    ) -> Mapping[str, Any] | None: ...


class PsycopgSimilarityRepository:
    def __init__(self, database_url: str):
        if psycopg is None or dict_row is None or Jsonb is None:
            raise RuntimeError(
                "Postgres support is unavailable. Install judge0_api requirements."
            )
        self.database_url = database_url

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=5,
                               options='-c statement_timeout=15000')

    def get_submission_scope(
        self,
        submission_id: str,
    ) -> Mapping[str, Any] | None:
        with self._connect() as connection:
            return connection.execute(
                """
                select
                  id,
                  assessment_id,
                  question_id,
                  student_id,
                  block_section_id
                from public.submissions
                where id = %s
                  and is_current
                """,
                (submission_id,),
            ).fetchone()

    def get_group_inputs(
        self,
        assessment_id: str,
        question_id: str,
    ) -> list[Mapping[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select
                  submission.id,
                  submission.student_id,
                  submission.block_section_id,
                  submission.verified_text,
                  submission.verified_version,
                  student.display_name as student_name,
                  block_section.name as block_section_name
                from public.submissions as submission
                join public.students as student
                  on student.id = submission.student_id
                join public.block_sections as block_section
                  on block_section.id = submission.block_section_id
                where submission.assessment_id = %s
                  and submission.question_id = %s
                  and submission.is_current
                  and submission.status in ('verified', 'graded')
                order by submission.id
                """,
                (assessment_id, question_id),
            ).fetchall()
        return list(rows)

    def get_starter_code(self, assessment_id: str, question_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                """
                select starter_code
                from public.assessment_questions
                where assessment_id = %s
                  and question_id = %s
                """,
                (assessment_id, question_id),
            ).fetchone()
        return str(row["starter_code"]) if row else ""

    def create_checking_scan(
        self,
        assessment_id: str,
        question_id: str,
        algorithm_version: str,
        cohort_fingerprint: str,
    ) -> Mapping[str, Any]:
        with self._connect() as connection:
            return connection.execute(
                """
                insert into public.similarity_scans (
                  assessment_id,
                  question_id,
                  status,
                  algorithm_version,
                  cohort_fingerprint
                )
                values (%s, %s, 'checking', %s, %s)
                returning *
                """,
                (
                    assessment_id,
                    question_id,
                    algorithm_version,
                    cohort_fingerprint,
                ),
            ).fetchone()

    def complete_scan(
        self,
        scan_id: str,
        matches: Sequence[Mapping[str, Any]],
        compared_count: int,
        skipped_count: int,
        cohort_fingerprint: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        with self._connect() as connection:
            for match in matches:
                connection.execute(
                    """
                    insert into public.similarity_matches (
                      scan_id,
                      lower_submission_id,
                      higher_submission_id,
                      lower_verified_version,
                      higher_verified_version,
                      match_type,
                      matched_token_count,
                      lower_coverage,
                      higher_coverage,
                      source_ranges
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        scan_id,
                        match["lower_submission_id"],
                        match["higher_submission_id"],
                        match["lower_verified_version"],
                        match["higher_verified_version"],
                        match["match_type"],
                        match["matched_token_count"],
                        match["lower_coverage"],
                        match["higher_coverage"],
                        Jsonb(match["source_ranges"]),
                    ),
                )

            connection.execute(
                """
                update public.similarity_scans
                set status = 'complete',
                    compared_pair_count = %s,
                    skipped_pair_count = %s,
                    cohort_fingerprint = %s,
                    metadata = %s,
                    completed_at = now(),
                    error_message = null
                where id = %s
                """,
                (
                    compared_count,
                    skipped_count,
                    cohort_fingerprint,
                    Jsonb(metadata or {}),
                    scan_id,
                ),
            )

    def fail_scan(self, scan_id: str, message: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                update public.similarity_scans
                set status = 'failed',
                    error_message = %s,
                    completed_at = now()
                where id = %s
                """,
                (message, scan_id),
            )

    def get_latest_scan(
        self,
        assessment_id: str,
        question_id: str,
    ) -> Mapping[str, Any] | None:
        with self._connect() as connection:
            scan = connection.execute(
                """
                select *
                from public.similarity_scans
                where assessment_id = %s
                  and question_id = %s
                order by created_at desc, id desc
                limit 1
                """,
                (assessment_id, question_id),
            ).fetchone()
            if scan is None:
                return None

            matches = connection.execute(
                """
                select
                  match.*,
                  lower_student.display_name as lower_student_name,
                  higher_student.display_name as higher_student_name,
                  lower_section.name as lower_block_section_name,
                  higher_section.name as higher_block_section_name
                from public.similarity_matches as match
                join public.similarity_scans as scan on scan.id = match.scan_id
                join public.submissions as lower_submission
                  on lower_submission.id = match.lower_submission_id
                join public.students as lower_student
                  on lower_student.id = lower_submission.student_id
                join public.block_sections as lower_section
                  on lower_section.id = lower_submission.block_section_id
                join public.submissions as higher_submission
                  on higher_submission.id = match.higher_submission_id
                join public.students as higher_student
                  on higher_student.id = higher_submission.student_id
                join public.block_sections as higher_section
                  on higher_section.id = higher_submission.block_section_id
                where match.scan_id = %s
                order by greatest(match.lower_coverage, match.higher_coverage) desc
                """,
                (scan["id"],),
            ).fetchall()

        return {**scan, "matches": list(matches)}

    def get_match_detail(
        self,
        scan_id: str,
        lower_submission_id: str,
        higher_submission_id: str,
    ) -> Mapping[str, Any] | None:
        with self._connect() as connection:
            return connection.execute(
                """
                select
                  match.*,
                  lower_submission.verified_text as lower_verified_text,
                  higher_submission.verified_text as higher_verified_text
                from public.similarity_matches as match
                join public.similarity_scans as scan on scan.id = match.scan_id
                join public.submissions as lower_submission
                  on lower_submission.id = match.lower_submission_id
                join public.submissions as higher_submission
                  on higher_submission.id = match.higher_submission_id
                where match.scan_id = %s
                  and match.lower_submission_id = %s
                  and match.higher_submission_id = %s
                  and lower_submission.verified_version = match.lower_verified_version
                  and higher_submission.verified_version = match.higher_verified_version
                  and lower_submission.is_current and higher_submission.is_current
                  and lower_submission.status in ('verified', 'graded')
                  and higher_submission.status in ('verified', 'graded')
                  and lower_submission.student_id <> higher_submission.student_id
                  and lower_submission.assessment_id = scan.assessment_id
                  and higher_submission.assessment_id = scan.assessment_id
                  and lower_submission.question_id = scan.question_id
                  and higher_submission.question_id = scan.question_id
                  and scan.status = 'complete'
                  and scan.id = (select latest.id from public.similarity_scans latest
                    where latest.assessment_id = scan.assessment_id and latest.question_id = scan.question_id
                    order by latest.created_at desc, latest.id desc limit 1)
                """,
                (scan_id, lower_submission_id, higher_submission_id),
            ).fetchone()
