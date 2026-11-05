from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas.plagiarism import PlagiarismCheckResponse
from app.services.file_parser import parse_uploaded_file
from app.services.plagiarism_service import check_plagiarism

router = APIRouter(prefix="/plagiarism", tags=["plagiarism"])


@router.post("/check", response_model=PlagiarismCheckResponse)
async def plagiarism_check(
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> PlagiarismCheckResponse:
    extracted_text = (text or "").strip()

    if file is not None:
        extracted_text = await parse_uploaded_file(file)

    if not extracted_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either text input or a supported file",
        )

    return check_plagiarism(extracted_text)