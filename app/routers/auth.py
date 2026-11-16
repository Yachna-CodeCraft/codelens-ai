from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.errors import DuplicateKeyError

from app.database import db
from app.schemas import Token, UserCreate
from app.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate):
    email = body.email.lower()
    try:
        result = await db.users.insert_one(
            {
                "email": email,
                "password_hash": hash_password(body.password),
                "created_at": datetime.now(timezone.utc),
            }
        )
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
    return {"id": str(result.inserted_id), "email": email}


@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    """`username` is the account email (keeps Swagger's Authorize button working)."""
    user = await db.users.find_one({"email": form.username.lower()})
    if not user or not verify_password(form.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return Token(access_token=create_access_token(str(user["_id"])))


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"id": str(user["_id"]), "email": user["email"]}
