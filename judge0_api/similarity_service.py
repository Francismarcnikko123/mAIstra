from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
import hashlib
import itertools
from typing import Any

try:
    from .similarity_checker import compare_c_code, prepare_c_code
    from .similarity_repository import SimilarityRepository
except ImportError:
    from similarity_checker import compare_c_code, prepare_c_code
    from similarity_repository import SimilarityRepository


ALGORITHM_VERSION = "c-tree-sitter-winnowing-v2"
CHECKING_TIMEOUT = timedelta(minutes=10)


class SimilarityError(RuntimeError):
    pass


class SubmissionNotFoundError(SimilarityError):
    pass


class MissingComparisonMetadataError(SimilarityError):
    pass


class MatchNotFoundError(SimilarityError):
    pass


def compute_cohort_fingerprint(
    submissions: Sequence[Mapping[str, Any]],
    starter_code: str,
) -> str:
    versions = sorted(
        f"{submission['id']}:{submission.get('verified_version', 0)}:"
        f"{submission.get('student_id')}:{submission.get('block_section_id')}"
        for submission in submissions
    )
    digest = hashlib.sha256()
    digest.update(ALGORITHM_VERSION.encode("utf-8"))
    digest.update(b"\0")
    digest.update((starter_code or "").encode("utf-8"))
    digest.update(b"\0")
    digest.update("\n".join(versions).encode("utf-8"))
    return digest.hexdigest()


class SimilarityService:
    def __init__(
        self,
        repository: SimilarityRepository,
        *,
        prepare: Callable[[str, str], Any] = prepare_c_code,
        compare: Callable[[Any, Any], dict[str, Any]] = compare_c_code,
        clock: Callable[[], datetime] | None = None,
    ):
        self.repository = repository
        self.prepare = prepare
        self.compare = compare
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def scan_submission(self, submission_id: str) -> dict[str, Any]:
        scope = self._required_scope(submission_id)
        assessment_id = str(scope["assessment_id"])
        question_id = str(scope["question_id"])
        submissions = self.repository.get_group_inputs(
            assessment_id,
            question_id,
        )
        starter_code = self.repository.get_starter_code(
            assessment_id,
            question_id,
        )
        fingerprint = compute_cohort_fingerprint(submissions, starter_code)
        scan = self.repository.create_checking_scan(
            assessment_id,
            question_id,
            ALGORITHM_VERSION,
            fingerprint,
        )
        scan_id = str(scan["id"])

        try:
            prepared = {
                str(submission["id"]): self.prepare(
                    str(submission["verified_text"]),
                    starter_code,
                )
                for submission in submissions
                if (submission.get("verified_text") or '').strip()
            }
            matches: list[dict[str, Any]] = []
            compared_count = 0
            skipped_count = 0
            skipped_reasons = {
                "missing_code": 0,
                "same_student": 0,
                "insufficient_evidence": 0,
                "partial_analysis": 0,
            }

            ordered_submissions = sorted(
                submissions,
                key=lambda submission: str(submission["id"]),
            )
            for lower, higher in itertools.combinations(ordered_submissions, 2):
                lower_id = str(lower["id"])
                higher_id = str(higher["id"])

                if str(lower.get("student_id")) == str(higher.get("student_id")):
                    skipped_count += 1
                    skipped_reasons["same_student"] += 1
                    continue
                if lower_id not in prepared or higher_id not in prepared:
                    skipped_count += 1
                    skipped_reasons["missing_code"] += 1
                    continue

                result = self.compare(prepared[lower_id], prepared[higher_id])
                if result.get("analysis_state") == "partial_analysis":
                    skipped_reasons["partial_analysis"] += 1
                    if result.get('match_type') != 'exact_duplicate':
                        skipped_count += 1
                        continue
                if result.get("match_type") == "insufficient_evidence":
                    skipped_count += 1
                    skipped_reasons["insufficient_evidence"] += 1
                    continue

                compared_count += 1
                if result.get("review_recommended"):
                    matches.append(
                        self._match_record(lower, higher, result)
                    )

            current_submissions = self.repository.get_group_inputs(
                assessment_id,
                question_id,
            )
            current_starter = self.repository.get_starter_code(
                assessment_id,
                question_id,
            )
            current_fingerprint = compute_cohort_fingerprint(
                current_submissions,
                current_starter,
            )
            if current_fingerprint != fingerprint:
                message = "The submission group changed during analysis. Retry the scan."
                self.repository.fail_scan(scan_id, message)
                return {
                    "status": "outdated",
                    "submission_id": submission_id,
                    "scan_id": scan_id,
                    "error": message,
                }

            self.repository.complete_scan(
                scan_id,
                matches,
                compared_count,
                skipped_count,
                fingerprint,
                metadata={"eligible_submission_count": len(prepared), "skipped_reasons": skipped_reasons},
            )
            return {
                "status": "complete",
                "submission_id": submission_id,
                "scan_id": scan_id,
                "assessment_id": assessment_id,
                "question_id": question_id,
                "eligible_submission_count": len(prepared),
                "compared_pair_count": compared_count,
                "skipped_pair_count": skipped_count,
                "skipped_reasons": skipped_reasons,
                "match_count": len(self._matches_for_submission(matches, submission_id)),
                "matches": self._matches_for_submission(matches, submission_id),
            }
        except Exception:
            self.repository.fail_scan(scan_id, "Similarity analysis failed.")
            raise

    def get_submission_summary(self, submission_id: str) -> dict[str, Any]:
        scope = self._scope(submission_id)
        if not self._has_complete_scope(scope):
            return {
                "status": "missing_metadata",
                "submission_id": submission_id,
                "error": "Missing comparison details",
            }

        assessment_id = str(scope["assessment_id"])
        question_id = str(scope["question_id"])
        submissions = self.repository.get_group_inputs(
            assessment_id,
            question_id,
        )
        starter_code = self.repository.get_starter_code(
            assessment_id,
            question_id,
        )
        fingerprint = compute_cohort_fingerprint(submissions, starter_code)
        scan = self.repository.get_latest_scan(assessment_id, question_id)

        if scan is None:
            return {
                "status": "not_checked",
                "submission_id": submission_id,
                "matches": [],
            }

        status = str(scan["status"])
        if status == "checking":
            started_at = self._as_datetime(scan.get("started_at"))
            if started_at is None or self.clock() - started_at > CHECKING_TIMEOUT:
                return {
                    "status": "unavailable",
                    "submission_id": submission_id,
                    "scan_id": str(scan["id"]),
                    "error": "The similarity check timed out. Retry the scan.",
                    "matches": [],
                }
        if status == "failed":
            return {
                "status": "unavailable",
                "submission_id": submission_id,
                "scan_id": str(scan["id"]),
                "error": scan.get("error_message") or "Similarity check failed.",
                "matches": [],
            }
        if scan.get("cohort_fingerprint") != fingerprint:
            return {
                "status": "outdated",
                "submission_id": submission_id,
                "scan_id": str(scan["id"]),
                "error": "Verified submissions changed after this check.",
                "matches": [],
            }

        return {
            "status": status,
            "submission_id": submission_id,
            "scan_id": str(scan["id"]),
            "compared_pair_count": scan.get(
                "compared_pair_count",
                0,
            ),
            "skipped_pair_count": scan.get(
                "skipped_pair_count",
                0,
            ),
            "eligible_submission_count": (scan.get('metadata') or {}).get('eligible_submission_count', 0),
            "skipped_reasons": (scan.get('metadata') or {}).get('skipped_reasons', {}),
            "matches": self._matches_for_submission(
                scan.get("matches", []),
                submission_id,
            ),
        }

    def get_match_detail(
        self,
        submission_id: str,
        peer_submission_id: str,
    ) -> dict[str, Any]:
        scope = self._required_scope(submission_id)
        peer_scope = self._required_scope(peer_submission_id)
        group = (str(scope["assessment_id"]), str(scope["question_id"]))
        peer_group = (
            str(peer_scope["assessment_id"]),
            str(peer_scope["question_id"]),
        )
        if group != peer_group:
            raise MatchNotFoundError("The submissions are not in the same group")

        summary = self.get_submission_summary(submission_id)
        if summary["status"] != "complete":
            raise MatchNotFoundError("No current similarity match is available")

        lower_id, higher_id = sorted((submission_id, peer_submission_id))
        detail = self.repository.get_match_detail(
            summary["scan_id"],
            lower_id,
            higher_id,
        )
        if detail is None:
            raise MatchNotFoundError("Similarity match not found")

        requested_is_lower = submission_id == lower_id
        source_ranges = detail.get("source_ranges") or {}
        return {
            "scan_id": summary["scan_id"],
            "submission_id": submission_id,
            "peer_submission_id": peer_submission_id,
            "match_type": detail["match_type"],
            "matched_token_count": detail["matched_token_count"],
            "submission_coverage": detail[
                "lower_coverage" if requested_is_lower else "higher_coverage"
            ],
            "peer_coverage": detail[
                "higher_coverage" if requested_is_lower else "lower_coverage"
            ],
            "submission_code": detail[
                "lower_verified_text"
                if requested_is_lower
                else "higher_verified_text"
            ],
            "peer_code": detail[
                "higher_verified_text"
                if requested_is_lower
                else "lower_verified_text"
            ],
            "submission_ranges": source_ranges.get('left' if requested_is_lower else 'right', []),
            "peer_ranges": source_ranges.get('right' if requested_is_lower else 'left', []),
        }

    def _scope(self, submission_id: str) -> Mapping[str, Any]:
        scope = self.repository.get_submission_scope(submission_id)
        if scope is None:
            raise SubmissionNotFoundError("Submission not found")
        return scope

    def _required_scope(self, submission_id: str) -> Mapping[str, Any]:
        scope = self._scope(submission_id)
        if not self._has_complete_scope(scope):
            raise MissingComparisonMetadataError("Missing comparison details")
        return scope

    @staticmethod
    def _has_complete_scope(scope: Mapping[str, Any]) -> bool:
        return all(
            scope.get(field)
            for field in (
                "assessment_id",
                "question_id",
                "student_id",
                "block_section_id",
            )
        )

    @staticmethod
    def _as_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    @staticmethod
    def _match_record(
        lower: Mapping[str, Any],
        higher: Mapping[str, Any],
        result: Mapping[str, Any],
    ) -> dict[str, Any]:
        ranges = {'left': result.get('left_ranges', []), 'right': result.get('right_ranges', [])}
        return {
            "lower_submission_id": str(lower["id"]),
            "higher_submission_id": str(higher["id"]),
            "lower_verified_version": int(lower["verified_version"]),
            "higher_verified_version": int(higher["verified_version"]),
            "match_type": result['match_type'],
            "matched_token_count": int(result["matched_token_count"]),
            "lower_coverage": float(result["left_coverage"]),
            "higher_coverage": float(result["right_coverage"]),
            "source_ranges": ranges,
            "lower_student_name": lower.get("student_name"),
            "higher_student_name": higher.get("student_name"),
            "lower_block_section_name": lower.get("block_section_name"),
            "higher_block_section_name": higher.get("block_section_name"),
        }

    @staticmethod
    def _matches_for_submission(
        matches: Sequence[Mapping[str, Any]],
        submission_id: str,
    ) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for match in matches:
            lower_id = str(match["lower_submission_id"])
            higher_id = str(match["higher_submission_id"])
            if submission_id not in {lower_id, higher_id}:
                continue
            requested_is_lower = submission_id == lower_id
            summaries.append(
                {
                    "peer_submission_id": (
                        higher_id if requested_is_lower else lower_id
                    ),
                    "peer_student_name": match.get(
                        "higher_student_name"
                        if requested_is_lower
                        else "lower_student_name"
                    ),
                    "peer_block_section_name": match.get(
                        "higher_block_section_name"
                        if requested_is_lower
                        else "lower_block_section_name"
                    ),
                    "match_type": match["match_type"],
                    "matched_token_count": match["matched_token_count"],
                    "submission_coverage": match[
                        "lower_coverage" if requested_is_lower else "higher_coverage"
                    ],
                    "peer_coverage": match[
                        "higher_coverage" if requested_is_lower else "lower_coverage"
                    ],
                }
            )
        return sorted(
            summaries,
            key=lambda match: (
                -max(match["submission_coverage"], match["peer_coverage"]),
                match["peer_submission_id"],
            ),
        )
