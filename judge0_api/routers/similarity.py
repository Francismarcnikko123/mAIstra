from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException

try:
    from ..similarity_repository import PsycopgSimilarityRepository
    from ..similarity_service import (
        MatchNotFoundError,
        MissingComparisonMetadataError,
        SimilarityService,
        SubmissionNotFoundError,
    )
except ImportError:
    from similarity_repository import PsycopgSimilarityRepository
    from similarity_service import (
        MatchNotFoundError,
        MissingComparisonMetadataError,
        SimilarityService,
        SubmissionNotFoundError,
    )


router = APIRouter(prefix="/api/similarity", tags=["similarity"])


def get_similarity_service() -> SimilarityService:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(
            status_code=503,
            detail=(
                "Similarity storage is not configured. Set DATABASE_URL for "
                "the Judge0 API service."
            ),
        )
    try:
        repository = PsycopgSimilarityRepository(database_url)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return SimilarityService(repository)


@router.post("/submissions/{submission_id}/scan")
def scan_submission(
    submission_id: str,
    service: SimilarityService = Depends(get_similarity_service),
):
    try:
        return service.scan_submission(submission_id)
    except MissingComparisonMetadataError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except SubmissionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Similarity check failed. Retry later.",
        ) from error


@router.get("/submissions/{submission_id}")
def get_submission_similarity(
    submission_id: str,
    service: SimilarityService = Depends(get_similarity_service),
):
    try:
        return service.get_submission_summary(submission_id)
    except SubmissionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/submissions/{submission_id}/matches/{peer_submission_id}")
def get_match_detail(
    submission_id: str,
    peer_submission_id: str,
    service: SimilarityService = Depends(get_similarity_service),
):
    try:
        return service.get_match_detail(submission_id, peer_submission_id)
    except (SubmissionNotFoundError, MatchNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except MissingComparisonMetadataError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
