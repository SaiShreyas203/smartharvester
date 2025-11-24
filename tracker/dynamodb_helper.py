"""
tracker/dynamodb_helper.py

Centralized DynamoDB helper used by the tracker app.

Provides:
- save_user_to_dynamodb(user_id_value, payload) / create_or_update_user(...) — persist users
- get_user_data_from_token(request_or_token) / get_user_id_from_token(...) — extract stable id
- save_planting_to_dynamodb(planting_dict) — persist planting, returns planting_id
- load_user_plantings(user_id) — query GSI user_id-index or fallback to Scan+Filter
- delete_planting_from_dynamodb(planting_id)
- update_user_notification_preference(username_or_userid, enabled)
- get_user_notification_preference(username_or_userid)

Notes:
- Reads configuration from environment variables:
    AWS_REGION, DYNAMO_USERS_TABLE, DYNAMO_PLANTINGS_TABLE, DYNAMO_USERS_PK
- Tries to be tolerant to missing AWS permissions (logs exceptions).
"""
from __future__ import annotations

import os
import json
import logging
import base64
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr

# Optional JWT decoding to extract claims without verification
try:
    import jwt as pyjwt  # PyJWT
except Exception:
    pyjwt = None  # type: ignore

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DYNAMO_USERS_TABLE = os.getenv("DYNAMO_USERS_TABLE", "users")
DYNAMO_PLANTINGS_TABLE = os.getenv("DYNAMO_PLANTINGS_TABLE", "plantings")
# Name of the partition key attribute for users table (if unknown, default to 'username' because console item showed username)
DYNAMO_USERS_PK = os.getenv("DYNAMO_USERS_PK", "username")


# ----- Dynamo resource / helpers -----
_dynamo_resource = None


def dynamo_resource():
    global _dynamo_resource
    if _dynamo_resource is None:
        _dynamo_resource = boto3.resource("dynamodb", region_name=AWS_REGION)
    return _dynamo_resource


def _table(name: str):
    return dynamo_resource().Table(name)


def _to_dynamo_decimal(obj: Any) -> Any:
    """Convert floats -> Decimal and recurse into lists/dicts. Remove None values at caller side."""
    if isinstance(obj, dict):
        return {k: _to_dynamo_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_dynamo_decimal(v) for v in obj]
    if isinstance(obj, float):
        return Decimal(str(obj))
    return obj


# ----- Users helpers -----
def save_user_to_dynamodb(user_id_value: str, payload: Dict[str, Any]) -> bool:
    """
    Persist a user into the users table.
    Ensures the configured partition key attribute (DYNAMO_USERS_PK) is present in the item.
    Also writes "user_id" attr in addition to the PK for consistency.
    Returns True on success, False on failure.
    """
    try:
        table = _table(DYNAMO_USERS_TABLE)
        item = dict(payload or {})
        # Ensure partition key attribute is present; if payload already contains it do not overwrite
        if DYNAMO_USERS_PK not in item:
            # If payload contains a username, use that; otherwise fall back to user_id_value
            if payload.get("username"):
                item[DYNAMO_USERS_PK] = str(payload.get("username"))
            else:
                item[DYNAMO_USERS_PK] = str(user_id_value)
        # Also set a consistent user_id attribute so plantings/user association can use it
        item.setdefault("user_id", str(user_id_value))
        # Convert numbers
        item = {k: _to_dynamo_decimal(v) for k, v in item.items() if v is not None}
        table.put_item(Item=item)
        logger.info("Saved user to DynamoDB [%s=%s]", DYNAMO_USERS_PK, item.get(DYNAMO_USERS_PK))
        return True
    except ClientError as e:
        logger.exception("DynamoDB ClientError in save_user_to_dynamodb: %s", e)
        return False
    except Exception as e:
        logger.exception("Unexpected error saving user to DynamoDB: %s", e)
        return False


def create_or_update_user(user_id: str, payload: Dict[str, Any]) -> bool:
    """
    Compatibility wrapper used by signals. Writes using save_user_to_dynamodb.
    """
    return save_user_to_dynamodb(user_id, payload)


def get_user_data_from_token(token_or_request: Union[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Best-effort extraction of user payload from a request or an id_token string.
    If a Django request with middleware that sets request.cognito_payload exists, use it.
    If a token string is supplied, decode (without verification) to extract claims.
    """
    try:
        # If it's a request-like object, check for common middleware attributes
        if not isinstance(token_or_request, str) and (hasattr(token_or_request, "META") or hasattr(token_or_request, "session")):
            req = token_or_request
            for attr in ("cognito_payload", "jwt_payload", "user_data", "cognito_user"):
                payload = getattr(req, attr, None)
                if payload:
                    if isinstance(payload, dict):
                        return payload
                    # sometimes middleware attaches an object with attributes
                    try:
                        return payload.__dict__
                    except Exception:
                        continue
            # If session contains id_token, try decode it
            id_token = None
            if hasattr(req, "session"):
                id_token = req.session.get("id_token")
            if id_token:
                return _decode_jwt_unverified(id_token)
            return None

        # Otherwise, treat token_or_request as a token string
        if isinstance(token_or_request, str):
            return _decode_jwt_unverified(token_or_request)

        return None
    except Exception as e:
        logger.exception("Error extracting user data from token/request: %s", e)
        return None


def _decode_jwt_unverified(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    try:
        if pyjwt:
            # decode without verification only to extract claims
            return pyjwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        # Fallback basic base64 decode of payload segment
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        padding = "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:
        logger.debug("JWT decode (unverified) failed: %s", e)
        return None


def get_user_id_from_token(token_or_request: Union[str, Any]) -> Optional[str]:
    """
    Returns the stable user identifier used in this app:
     - For Cognito users: the 'sub' claim from the id_token
     - For local Django-signup users: the 'user_id' or 'username' saved in session or request
    This function tries multiple locations and is best-effort.
    """
    try:
        # If request-like object, check middleware first
        if not isinstance(token_or_request, str) and (hasattr(token_or_request, "META") or hasattr(token_or_request, "session")):
            req = token_or_request
            # check middleware-attached payloads
            for attr in ("cognito_payload", "jwt_payload", "user_data"):
                payload = getattr(req, attr, None)
                if payload:
                    if isinstance(payload, dict):
                        return str(payload.get("sub") or payload.get("username") or payload.get("cognito:username") or payload.get("email") or payload.get("user_id") or "")
                    else:
                        # object-like payload
                        return str(getattr(payload, "sub", None) or getattr(payload, "username", None) or getattr(payload, "email", None) or getattr(payload, "user_id", None) or "")
            # session id_token
            if hasattr(req, "session"):
                if req.session.get("user_id"):
                    return str(req.session.get("user_id"))
                id_token = req.session.get("id_token")
                if id_token:
                    payload = _decode_jwt_unverified(id_token)
                    if payload:
                        return str(payload.get("sub") or payload.get("username") or payload.get("email") or payload.get("cognito:username") or "")
            # finally fall back to Django user pk if authenticated
            user = getattr(req, "user", None)
            if user and getattr(user, "is_authenticated", False):
                # Use django_<pk> scheme to differentiate from Cognito subs
                return f"django_{user.pk}"
            return None

        # If a token string was passed
        if isinstance(token_or_request, str):
            payload = _decode_jwt_unverified(token_or_request)
            if payload:
                return str(payload.get("sub") or payload.get("username") or payload.get("email") or "")
            return None

        return None
    except Exception as e:
        logger.exception("Error extracting user id from token/request: %s", e)
        return None


# ----- Plantings helpers -----
def save_planting_to_dynamodb(planting: Union[Dict[str, Any], object]) -> Optional[str]:
    """
    Save a planting record into the PLANTINGS table.
    Accepts dict or model instance. Ensures either user_id or username is present.
    Returns planting_id string on success, None on failure.
    """
    try:
        if isinstance(planting, dict):
            item = dict(planting)
            planting_id = item.get("planting_id") or item.get("id") or str(uuid.uuid4())
            item["planting_id"] = str(planting_id)
        else:
            obj = planting
            planting_id = str(getattr(obj, "pk", None) or getattr(obj, "id", None) or uuid.uuid4())
            item = {
                "planting_id": planting_id,
                "user_id": str(getattr(obj, "user_id", None) or ""),
                "username": getattr(obj, "username", None) or getattr(getattr(obj, "user", None), "username", None),
                "crop_name": getattr(obj, "crop_name", None),
                "planting_date": getattr(obj, "planting_date").isoformat() if getattr(obj, "planting_date", None) else None,
                "harvest_date": getattr(obj, "harvest_date").isoformat() if getattr(obj, "harvest_date", None) else None,
                "notes": getattr(obj, "notes", None),
                "batch_id": getattr(obj, "batch_id", None),
                "image_url": getattr(obj, "image_url", None),
                "plan": getattr(obj, "plan", None)
            }

        # Validate presence of username or user_id
        if not item.get("user_id") and not item.get("username"):
            logger.error("save_planting_to_dynamodb: missing both user_id and username; refusing to write: %s", item)
            return None

        # Convert numbers/decimals and remove None
        item = {k: _to_dynamo_decimal(v) for k, v in item.items() if v is not None}
        table = _table(DYNAMO_PLANTINGS_TABLE)
        table.put_item(Item=item)
        logger.info("Saved planting %s to DynamoDB (user: %s / username: %s)", item.get("planting_id"), item.get("user_id"), item.get("username"))
        return str(item.get("planting_id"))
    except ClientError as e:
        logger.exception("DynamoDB ClientError saving planting: %s", e)
        return None
    except Exception as e:
        logger.exception("Unexpected error saving planting to DynamoDB: %s", e)
        return None


def load_user_plantings(user_identifier: str) -> List[Dict[str, Any]]:
    """
    Load plantings for the provided user identifier.
    The identifier may be a user_id (Cognito sub or django_<pk>) or a username (table PK).
    Attempt these in order:
      1. Query GSI user_id-index using user_id (if index exists)
      2. Scan filter by user_id
      3. Scan filter by username
    Returns list of items (may be empty).
    """
    try:
        table = _table(DYNAMO_PLANTINGS_TABLE)
        # First, try to query by GSI (user_id-index) using identifier as user_id
        try:
            resp = table.query(IndexName="user_id-index", KeyConditionExpression=Key("user_id").eq(str(user_identifier)))
            items = resp.get("Items", []) or []
            if items:
                logger.debug("Loaded %d plantings for user_id via GSI", len(items))
                return items
        except ClientError as e:
            logger.debug("GSI query failed or not present: %s", e)
        except Exception as e:
            logger.debug("GSI query error: %s", e)

        # Fallback scan by user_id
        items = []
        scan_kwargs = {"FilterExpression": Attr("user_id").eq(str(user_identifier))}
        start_key = None
        while True:
            if start_key:
                scan_kwargs["ExclusiveStartKey"] = start_key
            resp = table.scan(**scan_kwargs)
            items.extend(resp.get("Items", []) or [])
            start_key = resp.get("LastEvaluatedKey")
            if not start_key:
                break
        if items:
            logger.debug("Scanned and found %d plantings for user_id", len(items))
            return items

        # Final fallback: scan by username (the users table PK)
        items = []
        scan_kwargs = {"FilterExpression": Attr("username").eq(str(user_identifier))}
        start_key = None
        while True:
            if start_key:
                scan_kwargs["ExclusiveStartKey"] = start_key
            resp = table.scan(**scan_kwargs)
            items.extend(resp.get("Items", []) or [])
            start_key = resp.get("LastEvaluatedKey")
            if not start_key:
                break
        logger.debug("Scanned and found %d plantings for username", len(items))
        return items
    except ClientError as e:
        logger.exception("DynamoDB ClientError loading plantings for %s: %s", user_identifier, e)
        return []
    except Exception as e:
        logger.exception("Unexpected error loading plantings for %s: %s", user_identifier, e)
        return []

def load_user_plantings(user_id: str) -> List[Dict[str, Any]]:
    """
    Return plantings for a given user_id.
    First tries a GSI named 'user_id-index'. If it doesn't exist or query fails,
    falls back to a Scan with FilterExpression (slower).
    """
    try:
        table = _table(DYNAMO_PLANTINGS_TABLE)
        # Try GSI query first
        try:
            resp = table.query(IndexName="user_id-index", KeyConditionExpression=Key("user_id").eq(str(user_id)))
            items = resp.get("Items", []) or []
            logger.debug("Queried %d plantings for user %s via GSI", len(items), user_id)
            return items
        except ClientError as e:
            logger.debug("GSI query failed for user_id=%s: %s. Falling back to scan.", user_id, e)
        except Exception as e:
            logger.debug("GSI query unexpected error: %s. Falling back to scan.", e)

        # Fallback: scan with filter
        items = []
        scan_kwargs = {"FilterExpression": Attr("user_id").eq(str(user_id))}
        start_key = None
        while True:
            if start_key:
                scan_kwargs["ExclusiveStartKey"] = start_key
            resp = table.scan(**scan_kwargs)
            items.extend(resp.get("Items", []) or [])
            start_key = resp.get("LastEvaluatedKey")
            if not start_key:
                break
        logger.debug("Scanned and found %d plantings for user %s", len(items), user_id)
        return items
    except ClientError as e:
        logger.exception("DynamoDB ClientError loading plantings for user %s: %s", user_id, e)
        return []
    except Exception as e:
        logger.exception("Unexpected error loading plantings for user %s: %s", user_id, e)
        return []


def delete_planting_from_dynamodb(planting_id: str) -> bool:
    try:
        table = _table(DYNAMO_PLANTINGS_TABLE)
        table.delete_item(Key={"planting_id": str(planting_id)})
        logger.info("Deleted planting %s from DynamoDB", planting_id)
        return True
    except ClientError as e:
        logger.exception("DynamoDB ClientError deleting planting %s: %s", planting_id, e)
        return False
    except Exception as e:
        logger.exception("Unexpected error deleting planting %s: %s", planting_id, e)
        return False


# ----- Notification preference helpers (stored on users table) -----
def update_user_notification_preference(username_or_userid: str, enabled: bool) -> bool:
    """
    Update notifications_enabled attribute on the users table for the given identity.
    Tries to update by DYNAMO_USERS_PK first; if not found, tries to find by scanning user_id.
    """
    try:
        table = _table(DYNAMO_USERS_TABLE)
        pk_name = DYNAMO_USERS_PK
        key = {pk_name: str(username_or_userid)}
        # Try UpdateItem directly (fast-path; works when username_or_userid equals PK value)
        try:
            table.update_item(
                Key=key,
                UpdateExpression="SET notifications_enabled = :v",
                ExpressionAttributeValues={":v": enabled},
            )
            logger.info("Updated notifications_enabled for %s via PK %s", username_or_userid, pk_name)
            return True
        except ClientError as e:
            logger.debug("UpdateItem by PK failed for %s: %s (will try scan fallback)", username_or_userid, e)

        # Fallback: scan for items with matching user_id attribute
        resp = table.scan(FilterExpression=Attr("user_id").eq(str(username_or_userid)), ProjectionExpression="#k", ExpressionAttributeNames={"#k": pk_name})
        items = resp.get("Items", []) or []
        for it in items:
            try:
                key = {pk_name: it.get(pk_name)}
                table.update_item(Key=key, UpdateExpression="SET notifications_enabled = :v", ExpressionAttributeValues={":v": enabled})
            except Exception:
                logger.exception("Failed to update notification pref for item: %s", it)
                continue
        logger.info("Updated notification preference for %d items matching user %s", len(items), username_or_userid)
        return True
    except Exception as e:
        logger.exception("Error updating user notification preference: %s", e)
        return False


def get_user_notification_preference(username_or_userid: str) -> bool:
    """
    Return stored notifications_enabled preference for the specified user.
    Defaults to True if not set or on error.
    """
    try:
        table = _table(DYNAMO_USERS_TABLE)
        pk_name = DYNAMO_USERS_PK
        # Try direct GetItem by PK
        try:
            resp = table.get_item(Key={pk_name: str(username_or_userid)})
            item = resp.get("Item")
            if item and "notifications_enabled" in item:
                return bool(item.get("notifications_enabled"))
        except ClientError:
            logger.debug("GetItem by PK failed for %s (will try scan)", username_or_userid)

        # Fallback: search by user_id attribute
        resp = table.scan(FilterExpression=Attr("user_id").eq(str(username_or_userid)), Limit=1)
        items = resp.get("Items", []) or []
        if items:
            return bool(items[0].get("notifications_enabled", True))
        return True
    except Exception as e:
        logger.exception("Error fetching notification preference for %s: %s", username_or_userid, e)
        return True
    
def get_user_plantings(user_id: str) -> List[Dict[str, Any]]:
    """
    Return plantings for a given user_id.
    First tries a GSI named 'user_id-index'. If it doesn't exist or query fails,
    falls back to a Scan with FilterExpression (slower).
    """
    try:
        table = _table(DYNAMO_PLANTINGS_TABLE)
        # Try GSI query first
        try:
            resp = table.query(IndexName="user_id-index", KeyConditionExpression=Key("user_id").eq(str(user_id)))
            items = resp.get("Items", []) or []
            logger.debug("Queried %d plantings for user %s via GSI", len(items), user_id)
            return items
        except ClientError as e:
            logger.debug("GSI query failed for user_id=%s: %s. Falling back to scan.", user_id, e)
        except Exception as e:
            logger.debug("GSI query unexpected error: %s. Falling back to scan.", e)

        # Fallback: scan with filter
        items = []
        scan_kwargs = {"FilterExpression": Attr("user_id").eq(str(user_id))}
        start_key = None
        while True:
            if start_key:
                scan_kwargs["ExclusiveStartKey"] = start_key
            resp = table.scan(**scan_kwargs)
            items.extend(resp.get("Items", []) or [])
            start_key = resp.get("LastEvaluatedKey")
            if not start_key:
                break
        logger.debug("Scanned and found %d plantings for user %s", len(items), user_id)
        return items
    except ClientError as e:
        logger.exception("DynamoDB ClientError loading plantings for user %s: %s", user_id, e)
        return []
    except Exception as e:
        logger.exception("Unexpected error loading plantings for user %s: %s", user_id, e)
        return []
    finally:
        return items    
    return []

def get_planting(user_id: str, planting_id: str) -> Dict[str, Any]:
    """
    Return a single planting for a given user_id and planting_id.
    First tries a GSI named 'user_id-index'. If it doesn't exist or query fails,
    falls back to a Scan with FilterExpression (slower).
    """
    try:
        table = _table(DYNAMO_PLANTINGS_TABLE)
        # Try GSI query first
        try:
            resp = table.query(IndexName="user_id-index", KeyConditionExpression=Key("user_id").eq(str(user_id)))
            items = resp.get("Items", []) or []     
            if items:
                for item in items:
                    if item.get("planting_id") == str(planting_id):
                        return item
        except ClientError as e:
            logger.debug("GSI query failed for user_id=%s: %s. Falling back to scan.", user_id, e)
        except Exception as e:
            logger.debug("GSI query unexpected error: %s. Falling back to scan.", e)

        # Fallback: scan with filter
        items = []
        scan_kwargs = {"FilterExpression": Attr("user_id").eq(str(user_id))}
        start_key = None
        while True:
            if start_key:
                scan_kwargs["ExclusiveStartKey"] = start_key            
            resp = table.scan(**scan_kwargs)
            items.extend(resp.get("Items", []) or [])
            start_key = resp.get("LastEvaluatedKey")
            if not start_key:
                break
        logger.debug("Scanned and found %d plantings for user %s", len(items), user_id)
        return items
    except ClientError as e:
        logger.exception("DynamoDB ClientError loading plantings for user %s: %s", user_id, e)
        return []
    except Exception as e:
        logger.exception("Unexpected error loading plantings for user %s: %s", user_id, e)
        return []   
    finally:
        return items
    return []   

