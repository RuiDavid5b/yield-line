"""
Wrapper over boto3's cognito-idp client for the direct-auth flows.
"""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

from stock_news.config import get_settings


class CognitoError(Exception):
    """Wraps a Cognito ClientError with a stable, non-AWS-specific message."""


def _client():
    return boto3.client("cognito-idp", region_name=get_settings().aws_region)


def sign_up(email: str, password: str) -> str:
    """Register a new user. Returns the Cognito sub (user id)."""
    settings = get_settings()
    try:
        response = _client().sign_up(
            ClientId=settings.cognito_client_id,
            Username=email,
            Password=password,
            UserAttributes=[{"Name": "email", "Value": email}],
        )
        return response["UserSub"]
    except ClientError as exc:
        raise CognitoError(_friendly_message(exc)) from exc


def confirm_sign_up(email: str, code: str) -> None:
    settings = get_settings()
    try:
        _client().confirm_sign_up(
            ClientId=settings.cognito_client_id, Username=email, ConfirmationCode=code
        )
    except ClientError as exc:
        raise CognitoError(_friendly_message(exc)) from exc


def initiate_auth(email: str, password: str) -> dict:
    """
    Returns the AuthenticationResult dict: AccessToken, IdToken,
    RefreshToken, ExpiresIn.
    """
    settings = get_settings()
    try:
        response = _client().initiate_auth(
            ClientId=settings.cognito_client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
        return response["AuthenticationResult"]
    except ClientError as exc:
        raise CognitoError(_friendly_message(exc)) from exc


def refresh_auth(refresh_token: str) -> dict:
    settings = get_settings()
    try:
        response = _client().initiate_auth(
            ClientId=settings.cognito_client_id,
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={"REFRESH_TOKEN": refresh_token},
        )
        return response["AuthenticationResult"]
    except ClientError as exc:
        raise CognitoError(_friendly_message(exc)) from exc


def get_user(access_token: str) -> dict:
    try:
        return _client().get_user(AccessToken=access_token)
    except ClientError as exc:
        raise CognitoError(_friendly_message(exc)) from exc


def global_sign_out(access_token: str) -> None:
    try:
        _client().global_sign_out(AccessToken=access_token)
    except ClientError as exc:
        raise CognitoError(_friendly_message(exc)) from exc


def _friendly_message(exc: ClientError) -> str:
    code = exc.response.get("Error", {}).get("Code", "")
    return {
        "UsernameExistsException": "An account with this email already exists.",
        "NotAuthorizedException": "Incorrect email or password.",
        "UserNotConfirmedException": "Please verify your email before logging in.",
        "CodeMismatchException": "Invalid verification code.",
        "ExpiredCodeException": "Verification code has expired.",
        "UserNotFoundException": "Incorrect email or password.",
    }.get(code, "Authentication failed.")
