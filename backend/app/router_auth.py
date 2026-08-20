"""Auth endpoints: login + current user."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginIn):
    user = auth.authenticate(body.username, body.password)
    if not user:
        raise HTTPException(401, "Invalid username or password")
    token = auth.make_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "username": user["username"],
                 "role": user["role"], "full_name": user["full_name"]},
    }


@router.get("/me")
def me(user: dict = Depends(auth.get_current_user)):
    return user
