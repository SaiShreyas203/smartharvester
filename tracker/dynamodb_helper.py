"""
DynamoDB helper utilities used by tracker views.

Provides:
- load_user_plantings(user_id): returns a list of planting items for the given user_id
- get_user_id_from_request(request): best-effort extraction of the user id from request/session/token

Notes:
- Requires boto3 installed and AWS credentials available to the Django process.
- Tries to query a GSI named 'user_id-index' on the plantings table; if not present it falls back to a scan.
- For JWT decoding (Authorization header), PyJWT is used if installed; if not available, the token payload is not decoded.
"""
from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

# Optional JWT decode library - used only to parse token payload without verifying signature.
try:
    import jwt  # PyJWT
except Exception:
    jwt = None  # safe fallback

from boto3.dynamodb.conditions import Key, Attr

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
        # If the Index doesn't exist or another client error happened, log and try the scan fallback.
        logger.debug("Query by GSI failed for user_id %s: %s. Falling back to scan.", user_key, e)
    except Exception as exc:
        logger.exception("Unexpected error querying GSI for user_id %s: %s", user_key, exc)

    # Fallback: scan with filter (slower). Good for small tables or development.
    try:
        items: List[Dict[str, Any]] = []
        # Use pagination for safety
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
                # payload may be dict or object with attributes
                if isinstance(payload, dict):
                    user_id = payload.get("sub") or payload.get("username") or payload.get("email")
                    if user_id:
                        return str(user_id)
                else:
                    # object-like
                    user_id = getattr(payload, "sub", None) or getattr(payload, "username", None)
                    if user_id:
                        return str(user_id)

        # 2) Django authenticated user
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            try:
                return str(user.pk)
            except Exception:
                # fallback to username if pk not serializable
                return getattr(user, "username", None)

        # 3) Authorization header -> Bearer token -> decode JWT (no signature verification)
        auth_header = request.META.get("HTTP_AUTHORIZATION") or request.headers.get("Authorization", "")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
                if jwt:
                    try:
                        # decode without verifying signature (use only for extracting claims; do NOT trust blindly)
                        payload = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
                        user_id = payload.get("sub") or payload.get("username") or payload.get("cognito:username") or payload.get("email")
                        if user_id:
                            return str(user_id)
                    except Exception as exc:
                        logger.debug("JWT decode failed (unverified) for Authorization token: %s", exc)
                else:
                    logger.debug("PyJWT not installed; cannot decode Authorization JWT to extract user id.")
        return None
    except Exception as exc:
        logger.exception("Error while extracting user id from request: %s", exc)
        return None