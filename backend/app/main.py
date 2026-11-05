from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.references import router as references_router
from app.api.routes.health import router as health_router
from app.api.routes.plagiarism import router as plagiarism_router
from app.services.corpus_indexer import load_index


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.index_status = {
        "status": "loading",
        "documents_indexed": 0,
        "chunks_indexed": 0,
    }

    try:
        records, embeddings, index = load_index()

        documents_indexed = len({record.document_id for record in records})
        chunks_indexed = len(records)

        app.state.index_status = {
            "status": "ready",
            "documents_indexed": documents_indexed,
            "chunks_indexed": chunks_indexed,
        }

        print(
            f"Loaded index: {documents_indexed} documents / "
            f"{chunks_indexed} chunks"
        )

    except Exception as exc:
        app.state.index_status = {
            "status": "error",
            "documents_indexed": 0,
            "chunks_indexed": 0,
            "message": str(exc),
        }

        print(f"Index startup failed: {exc}")

    yield


app = FastAPI(
    title="Plagiarism Detection API",
    version="0.1.0",
    description="Deployment-ready text plagiarism detection API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(references_router, prefix="/api")
app.include_router(plagiarism_router, prefix="/api")


@app.get("/")
def root() -> dict[str, object]:
    return {
        "message": "Plagiarism Detection API is running",
        "docs_url": "/docs",
        "health_url": "/api/health",
        "plagiarism_check_url": "/api/plagiarism/check",
        "index_status": app.state.index_status,
    }