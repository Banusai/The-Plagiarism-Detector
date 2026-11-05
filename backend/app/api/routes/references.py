from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import MAX_FILES_PER_UPLOAD
from app.services.admin_auth import bearer_scheme, require_admin
from app.services.reference_service import list_reference_documents, upload_reference_documents

router = APIRouter(prefix="/references", tags=["reference-documents"])


def _admin_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    return require_admin(credentials)


@router.get("")
def get_reference_documents(
    _: Annotated[str, Depends(_admin_user)],
) -> dict:
    documents = list_reference_documents()
    return {"total": len(documents), "documents": documents}


@router.post("/upload")
def add_reference_documents(
    _: Annotated[str, Depends(_admin_user)],
    files: Annotated[list[UploadFile], File(description=f"Upload 1 to {MAX_FILES_PER_UPLOAD} PDF or TXT files")],
) -> dict:
    return upload_reference_documents(files)
