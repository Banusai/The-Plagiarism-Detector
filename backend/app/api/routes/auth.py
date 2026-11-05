from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.admin_auth import authenticate_admin

router = APIRouter(prefix="/admin", tags=["admin-auth"])


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


@router.post("/login")
def admin_login(payload: AdminLoginRequest) -> dict[str, str]:
    token = authenticate_admin(payload.username, payload.password)
    return {"access_token": token, "token_type": "bearer"}
