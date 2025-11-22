"""
DynamoDB helper utilities used by tracker views.

This file provides:
- load_user_plantings(user_id): returns a list of planting items for the given user_id
- get_user_id_from_request(request): best-effort extraction of a user id from a Django request
- get_user_id_from_token(token_or_request): compatibility helper the app expects; accepts either a token string
  or a Django request object and returns the user id (sub/username/email) or None.

Notes:
- JWT decoding is done WITHOUT verifying the signature (only to extract claims). This is intended only for
  identifying the user id from a token, not for authentication/authorization trust decisions.
- If PyJWT (jwt) is installed we use it; otherwise we fall back to a minimal base64-url decode of the token payload.
- load_user_plantings will try a GSI named 'user_id-index' and fallback to scan if necessary.
"""
from __future__ import annotations

import os
import json
import logging
import base64
from typing import Any, Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr

# Optional PyJWT - use if available (convenient)
try:
    import jwt  # PyJWT
except Exception:
    jwt = None  # type: ignore

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
PLANTINGS_TABLE = os.getenv("DYNAMO_PLANTINGS_TABLE", "plantings")
USERS_TABLE = os.getenv("DYNAMO_USERS_TABLE", "users")


def _dynamo_resource():
    """Return a boto3 DynamoDB resource."""
    return boto3.resource("dynamodb", region_name=AWS_REGION)


def _table(name: str):
    """Return a DynamoDB Table resource."""
    return _dynamo_resource().Table(name)


def load_user_plantings(user_id: str) -> List[Dict[str, Any]]:
    """
    Load plantings for a specific user_id from the PLANTINGS_TABLE.

    Attempt order:
      1. Query a GSI called 'user_id-index' (fast, recommended).
      2. Fallback to Scan with FilterExpression on attribute 'user_id' (slower).

    Returns a list of items (possibly empty). Errors are logged and an empty list is returned.
    """
    user_key = str(user_id)
    table = _table(PLANTINGS_TABLE)
    # Try query on GSI first (recommended). If the index doesn't exist a ClientError/ValidationException will be raised.
    try:
        resp = table.query(
            IndexName="user_id-index",
            KeyConditionExpression=Key("user_id").eq(user_key),
        )
        items = resp.get("Items", []) or []
        logger.debug("Queried %d items for user_id %s using GSI", len(items), user_key)
        return items
    except ClientError as e:
        logger.debug("Query by GSI failed for user_id %s: %s. Falling back to scan.", user_key, e)
    except Exception as exc:
        logger.exception("Unexpected error querying GSI for user_id %s: %s", user_key, exc)

    # Fallback: scan with filter (slower). Good for small tables or development.
    try:
        items: List[Dict[str, Any]] = []
        scan_kwargs = {"FilterExpression": Attr("user_id").eq(user_key)}
        done = False
        start_key = None
        while not done:
            if start_key:
                scan_kwargs["ExclusiveStartKey"] = start_key
            resp = table.scan(**scan_kwargs)
            items.extend(resp.get("Items", []) or [])
            start_key = resp.get("LastEvaluatedKey")
            done = start_key is None
        logger.debug("Scanned and found %d items for user_id %s", len(items), user_key)
        return items
    except ClientError as e:
        logger.exception("DynamoDB scan failed for user_id %s: %s", user_key, e)
        return []
    except Exception as exc:
        logger.exception("Unexpected error scanning plantings for user_id %s: %s", user_key, exc)
        return []


def get_user_id_from_request(request) -> Optional[str]:
    """
    Extract a user identifier from the request.

    Order of attempts:
      1. If middleware attached a cognito payload or jwt payload to request (common names: request.cognito_payload, request.jwt_payload),
         return its 'sub' or 'username' claim.
      2. If request.user is authenticated, return request.user.pk
      3. If Authorization: Bearer <token> header exists, attempt to decode JWT payload (without verifying signature) and return 'sub' or 'username'
      4. Otherwise return None

    This function is best-effort and does NOT throw; it logs issues and returns None when it cannot determine the user_id.
    """
    try:
        # 1) Middleware-attached payloads (common patterns)
        for attr in ("cognito_payload", "jwt_payload", "cognito_user", "cognito_jwt"):
            payload = getattr(request, attr, None)
            if payload:
                if isinstance(payload, dict):
                    user_id = payload.get("sub") or payload.get("username") or payload.get("email")
                    if user_id:
                        return str(user_id)
                else:
                    user_id = getattr(payload, "sub", None) or getattr(payload, "username", None)
                    if user_id:
                        return str(user_id)

        # 2) Django authenticated user
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            try:
                return str(user.pk)
            except Exception:
                return getattr(user, "username", None)

        # 3) Authorization header -> Bearer token -> decode JWT (no signature verification)
        auth_header = None
        # Django < 3.2 uses request.META; newer may have request.headers
        if hasattr(request, "META"):
            auth_header = request.META.get("HTTP_AUTHORIZATION")
        if not auth_header and hasattr(request, "headers"):
            auth_header = request.headers.get("Authorization")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
                return _extract_userid_from_jwt(token)
        return None
    except Exception as exc:
        logger.exception("Error while extracting user id from request: %s", exc)
        return None


def _extract_userid_from_jwt(token: str) -> Optional[str]:
    """
    Extract likely user id claims from a JWT token without verifying the signature.
    Returns sub/username/cognito:username/email if found.
    """
    if not token:
        return None
    try:
        if jwt:
            # use PyJWT to decode without verification
            payload = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        else:
            # Fallback: base64url decode the payload part
            parts = token.split(".")
            if len(parts) < 2:
                logger.debug("Token does not appear to be a JWT (no dot).")
                return None
            payload_b64 = parts[1]
            # Add padding if needed
            padding = "=" * (-len(payload_b64) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
            payload = json.loads(payload_bytes.decode("utf-8"))
        # Common claim names to identify the user
        user_id = payload.get("sub") or payload.get("username") or payload.get("cognito:username") or payload.get("email")
        if user_id:
            return str(user_id)
        # sometimes 'claims' nested
        if "claims" in payload and isinstance(payload["claims"], dict):
            claims = payload["claims"]
            user_id = claims.get("sub") or claims.get("username") or claims.get("email")
            if user_id:
                return str(user_id)
        return None
    except Exception as exc:
        logger.debug("Failed to extract userid from JWT (no verify): %s", exc)
        return None


def get_user_id_from_token(token_or_request: Union[str, Any]) -> Optional[str]:
    """
    Compatibility helper expected by some views.

    Accepts:
      - a Django request object -> delegates to get_user_id_from_request
      - a string token (JWT) -> attempts to decode payload and extract user id (no verification)

    Returns: user id string (sub/username/email) or None
    """
    try:
        # If it's a request-like object (has META or headers), treat accordingly
        if not isinstance(token_or_request, str) and (hasattr(token_or_request, "META") or hasattr(token_or_request, "headers")):
            return get_user_id_from_request(token_or_request)
        # Otherwise assume it's a token string
        if isinstance(token_or_request, str):
            return _extract_userid_from_jwt(token_or_request)
        return None
    except Exception as exc:
        logger.exception("Error in get_user_id_from_token: %s", exc)
        return None