from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr

from stock_news.api.models import ApiKeyStatusOut, SetApiKeyBody
from stock_news.auth.cognito_client import (
    CognitoError,
    confirm_sign_up,
    global_sign_out,
    initiate_auth,
    sign_up,
)
from stock_news.auth.crypto import encrypt_api_key
from stock_news.auth.dependencies import (
    SESSION_COOKIE_NAME,
    get_current_session,
    require_csrf,
)
from stock_news.auth.session import create_session, delete_session
from stock_news.auth.token_verification import verify_id_token
from stock_news.storage.db import get_session_factory
from stock_news.storage.loaders import (
    clear_user_api_key,
    get_or_create_user,
    get_user_api_key_encrypted,
    set_user_api_key,
)

_session_factory = get_session_factory()

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_MAX_AGE = 30 * 24 * 60 * 60


class RegisterBody(BaseModel):
    email: EmailStr
    password: str


class VerifyBody(BaseModel):
    email: EmailStr
    code: str


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    email: str
    csrf_token: str


class MessageResponse(BaseModel):
    message: str


class MeResponse(BaseModel):
    email: str


class CsrfResponse(BaseModel):
    csrf_token: str


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(body: RegisterBody):
    try:
        sign_up(body.email, body.password)
    except CognitoError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"message": "Check your email for a verification code."}


@router.post(
    "/verify",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
def verify(body: VerifyBody):
    try:
        confirm_sign_up(body.email, body.code)
    except CognitoError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"message": "Email verified. You can now log in."}


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(body: LoginBody, response: Response):
    try:
        auth_result = initiate_auth(body.email, body.password)
    except CognitoError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    try:
        claims = verify_id_token(auth_result["IdToken"])
    except jwt.InvalidTokenError:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token verification failed",
        )
    user_sub = claims["sub"]

    with _session_factory() as db_session:
        get_or_create_user(db_session, user_sub, body.email)
        db_session.commit()

    session_id, csrf_token = create_session(user_sub, body.email, auth_result)

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
    )
    return {"email": body.email, "csrf_token": csrf_token}


@router.get(
    "/me",
    response_model=MeResponse,
)
def me(session: dict = Depends(get_current_session)):
    return {"email": session["email"]}


@router.put(
    "/me/api-key", status_code=status.HTTP_200_OK, dependencies=[Depends(require_csrf)]
)
def set_api_key(
    body: SetApiKeyBody,
    session: dict = Depends(get_current_session),
):
    with _session_factory() as db_session:
        user = get_or_create_user(
            db_session,
            session["user_sub"],
            session["email"],
        )

        encrypted = encrypt_api_key(body.api_key)

        set_user_api_key(
            db_session,
            user["id"],
            body.provider,
            body.model,
            encrypted,
        )

        db_session.commit()

    return {"message": "API key saved."}


@router.delete(
    "/me/api-key", status_code=status.HTTP_200_OK, dependencies=[Depends(require_csrf)]
)
def delete_api_key(session: dict = Depends(get_current_session)):
    with _session_factory() as db_session:
        user = get_or_create_user(db_session, session["user_sub"], session["email"])
        clear_user_api_key(db_session, user["id"])
        db_session.commit()
    return {"message": "API key removed."}


@router.get("/me/api-key", response_model=ApiKeyStatusOut)
def get_api_key_status(session: dict = Depends(get_current_session)):
    with _session_factory() as db_session:
        user = get_or_create_user(
            db_session,
            session["user_sub"],
            session["email"],
        )

        stored = get_user_api_key_encrypted(
            db_session,
            user["id"],
        )

    if stored is None:
        return {
            "provider": None,
            "model": None,
            "has_key": False,
        }

    return {
        "provider": stored["llm_provider"],
        "model": stored["llm_model"],
        "has_key": True,
    }


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_csrf)],
)
def logout(response: Response, session: dict = Depends(get_current_session)):
    try:
        global_sign_out(session["access_token"])
    except CognitoError:
        pass
    delete_session(session["session_id"])
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"message": "Logged out."}


@router.get(
    "/csrf",
    response_model=CsrfResponse,
)
def csrf(session: dict = Depends(get_current_session)):
    return {"csrf_token": session["csrf_token"]}
