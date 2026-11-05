from __future__ import annotations

import io
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader

from app.core.config import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
)
from app.services.chunking import clean_text


def _validate_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file extension: {suffix}. Only PDF and TXT are supported.",
        )
    return suffix


def _validate_content_type(content_type: str | None) -> None:
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {content_type}",
        )


def _extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\\n".join(pages).strip()


def parse_file_bytes(filename: str, content_type: str | None, file_bytes: bytes) -> str:
    suffix = _validate_extension(filename)
    _validate_content_type(content_type)

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum allowed size is 5 MB per file.",
        )

    try:
        if suffix == ".pdf":
            text = _extract_pdf_text(file_bytes)
        else:
            text = file_bytes.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TXT files must use UTF-8 encoding.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read uploaded file: {exc}",
        ) from exc

    text = clean_text(text)
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No readable text could be extracted from file.",
        )
    return text


async def parse_uploaded_file(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename",
        )
    file_bytes = await file.read(MAX_FILE_SIZE_BYTES + 1)
    return parse_file_bytes(file.filename, file.content_type, file_bytes)
