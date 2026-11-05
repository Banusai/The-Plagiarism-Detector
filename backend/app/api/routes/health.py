from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(request: Request) -> dict[str, object]:
    index_status = getattr(
        request.app.state,
        "index_status",
        {
            "status": "unknown",
            "documents_indexed": 0,
            "chunks_indexed": 0,
            "message": "Index status not initialized",
        },
    )

    return {
        "status": "ok",
        "service": "plagiarism-detection-api",
        "index": index_status,
    }