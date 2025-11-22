"""
DynamoDB helper utilities used by tracker views.

Includes:
- load_user_plantings(user_id)
- get_user_id_from_request(request)
- get_user_id_from_token(token_or_request)
- save_planting_to_dynamodb(planting_or_dict)

This file does NOT import Django models at top-level to avoid circular imports.
"""
from __future__ import annotations

import os
import json
import logging
import base64
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr

# Optional PyJWT - used only for convenience if available
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
    return boto3.resource("dynamodb", region_name=AWS_REGION)


def _table(name: str):
    return _dynamo_resource().Table(name)


def _to_dynamo_compatible(value: Any) -> Any:
    """
    Convert Python values to DynamoDB compatible types (Decimal for floats).
    Recurses into lists/dicts.
    """
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamo_compatible(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_to_dynamo_compatible(v) for v in value]
    return value


def load_user_plantings(user_id: str) -> List[Dict[str, Any]]:
    user_key = str(user_id)
    table = _table(PLANTINGS_TABLE)
    try:
        resp = table.query(IndexName="user_id-index", KeyConditionExpression=Key("user_id").eq(user_key))
        items = resp.get("Items", []) or []
        logger.debug("Queried %d items for user_id %s using GSI", len(items), user_key)
        return items
    except ClientError as e:
        logger.debug("Query by GSI failed for user_id %s: %s. Falling back to scan.", user_key, e)
    except Exception as exc:
        logger.exception("Unexpected error querying GSI for user_id %s: %s", user_key, exc)

    # Fallback to scan
    try:
        items: List[Dict[str, Any]] = []
        scan_kwargs = {"FilterExpression": Attr("user_id").eq(user_key)}
        start_key = None
        while True:
            if start_key:
                scan_kwargs["ExclusiveStartKey"] = start_key
            resp = table.scan(**scan_kwargs)
            items.extend(resp.get("Items", []) or [])
            start_key = resp.get("LastEvaluatedKey")
            if not start_key:
                break
        logger.debug("Scanned and found %d items for user_id %s", len(items), user_key)
        return items
    except ClientError as e:
        logger.exception("DynamoDB scan failed for user_id %s: %s", user_key, e)
        return []
    except Exception as exc:
        logger.exception("Unexpected error scanning plantings for user_id %s: %s", user_key, exc)
        return []


def _extract_userid_from_jwt(token: str) -> Optional[str]:
    if not token:
        return None
    try:
        if jwt:
            payload = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        else:
            parts = token.split(".")
            if len(parts) < 2:
                return None
            payload_b64 = parts[1]
            padding = "=" * (-len(payload_b64) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
            payload = json.loads(payload_bytes.decode("utf-8"))
        user_id = payload.get("sub") or payload.get("username") or payload.get("cognito:username") or payload.get("email")
        if user_id:
            return str(user_id)
        if "claims" in payload and isinstance(payload["claims"], dict):
            claims = payload["claims"]
            return str(claims.get("sub") or claims.get("username") or claims.get("email")) if (claims.get("sub") or claims.get("username") or claims.get("email")) else None
        return None
    except Exception as exc:
        logger.debug("Failed to extract userid from JWT: %s", exc)
        return None


def get_user_id_from_request(request) -> Optional[str]:
    try:
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
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            try:
                return str(user.pk)
            except Exception:
                return getattr(user, "username", None)
        auth_header = None
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


def get_user_id_from_token(token_or_request: Union[str, Any]) -> Optional[str]:
    try:
        if not isinstance(token_or_request, str) and (hasattr(token_or_request, "META") or hasattr(token_or_request, "headers")):
            return get_user_id_from_request(token_or_request)
        if isinstance(token_or_request, str):
            return _extract_userid_from_jwt(token_or_request)
        return None
    except Exception as exc:
        logger.exception("Error in get_user_id_from_token: %s", exc)
        return None


def save_planting_to_dynamodb(planting_or_dict: Union[Dict[str, Any], object]) -> bool:
    """
    Save a planting to the PLANTINGS_TABLE in DynamoDB.

    Accepts either:
      - a dict with keys (planting_id, user_id, crop_name, planting_date, harvest_date, notes, batch_id, image_url, ...)
      - a Django model instance (Planting) - the function will read common attributes.
    Returns True on success, False otherwise.
    """
    try:
        # Build item dictionary from either an object or a dict
        if isinstance(planting_or_dict, dict):
            item = dict(planting_or_dict)
            # prefer 'planting_id' key, fallback to 'id'
            item.setdefault("planting_id", str(item.get("id") or item.get("pk") or item.get("planting_id")))
        else:
            # lazy import of Django model fields to avoid circular imports
            # Expect planting_or_dict to have attributes: pk, user_id/user, crop_name, planting_date, harvest_date, notes, batch_id, image or image_url
            obj = planting_or_dict
            item = {
                "planting_id": str(getattr(obj, "pk", None) or getattr(obj, "id", None)),
                "user_id": str(getattr(obj, "user_id", None) or getattr(getattr(obj, "user", None), "pk", None) or getattr(obj, "user", None)),
                "crop_name": getattr(obj, "crop_name", None),
                "planting_date": getattr(obj, "planting_date").isoformat() if getattr(obj, "planting_date", None) else None,
                "harvest_date": getattr(obj, "harvest_date").isoformat() if getattr(obj, "harvest_date", None) else None,
                "notes": getattr(obj, "notes", None),
                "batch_id": getattr(obj, "batch_id", None),
            }
            # Try image_url attribute or model ImageField .url if present
            image_url = None
            if getattr(obj, "image_url", None):
                image_url = getattr(obj, "image_url")
            else:
                image_field = getattr(obj, "image", None)
                try:
                    if image_field and hasattr(image_field, "url"):
                        image_url = image_field.url
                except Exception:
                    # storage backend might raise until saved; ignore
                    image_url = None
            if image_url:
                item["image_url"] = image_url

        # Clean - remove None values and convert floats to Decimal
        item = {k: _to_dynamo_compatible(v) for k, v in item.items() if v is not None and k != ""}
        if "planting_id" not in item:
            logger.error("save_planting_to_dynamodb: planting_id missing - item=%s", item)
            return False

        table = _table(PLANTINGS_TABLE)
        table.put_item(Item=item)
        logger.info("Saved planting %s to DynamoDB table %s", item.get("planting_id"), PLANTINGS_TABLE)
        return True
    except ClientError as e:
        logger.exception("DynamoDB ClientError saving planting: %s", e)
        return False
    except Exception as exc:
        logger.exception("Unexpected error saving planting to DynamoDB: %s", exc)
        return False