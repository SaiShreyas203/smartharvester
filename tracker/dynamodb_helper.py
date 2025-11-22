# tracker/dynamodb_helper.py
from __future__ import annotations
import os, json, base64, logging, uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr

# Optional PyJWT
try:
    import jwt  # PyJWT
except Exception:
    jwt = None  # type: ignore

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
USERS_TABLE = os.getenv("DYNAMO_USERS_TABLE", "users")
PLANTINGS_TABLE = os.getenv("DYNAMO_PLANTINGS_TABLE", "plantings")

def _dynamo_resource():
    return boto3.resource("dynamodb", region_name=AWS_REGION)

def _table(name: str):
    return _dynamo_resource().Table(name)

def _to_dynamo_compatible(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamo_compatible(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_to_dynamo_compatible(v) for v in value]
    return value

# -------- Users --------
def create_or_update_user(user_id: str, payload: Dict[str, Any]) -> bool:
    """
    Create or update a user item in the USERS_TABLE.
    Partition key expected: 'user_id' — change if your table uses a different PK.
    """
    try:
        table = _table(USERS_TABLE)
        item = {"user_id": str(user_id)}
        item.update(payload)
        item = _to_dynamo_compatible(item)
        table.put_item(Item=item)
        logger.info("Wrote user %s to Dynamo", user_id)
        return True
    except ClientError as e:
        logger.exception("DynamoDB put_item(user) failed: %s", e)
        return False

# -------- Plantings --------
def save_planting_to_dynamodb(planting: Union[Dict[str, Any], object]) -> Optional[str]:
    """
    Accepts a dict or a model instance. Stores into PLANTINGS_TABLE.
    Returns planting_id string on success, otherwise None.
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
                "user_id": str(getattr(obj, "user_id", None) or getattr(getattr(obj, "user", None), "pk", None) or ""),
                "crop_name": getattr(obj, "crop_name", None),
                "planting_date": getattr(obj, "planting_date").isoformat() if getattr(obj, "planting_date", None) else None,
                "harvest_date": getattr(obj, "harvest_date").isoformat() if getattr(obj, "harvest_date", None) else None,
                "notes": getattr(obj, "notes", None),
                "batch_id": getattr(obj, "batch_id", None),
                "image_url": getattr(obj, "image_url", None),
            }
        # Clean and convert
        item = {k: _to_dynamo_compatible(v) for k, v in item.items() if v is not None and k != ""}
        if "planting_id" not in item:
            item["planting_id"] = str(uuid.uuid4())
        # Ensure user_id exists for access control (may be empty if session-only)
        table = _table(PLANTINGS_TABLE)
        table.put_item(Item=item)
        logger.info("Saved planting %s to Dynamo", item["planting_id"])
        return str(item["planting_id"])
    except ClientError as e:
        logger.exception("DynamoDB put_item(planting) failed: %s", e)
        return None
    except Exception as e:
        logger.exception("Unexpected error saving planting to Dynamo: %s", e)
        return None

def load_user_plantings(user_id: str) -> List[Dict[str, Any]]:
    """
    Return list of plantings for a specific user_id.
    Queries GSI 'user_id-index' if present; otherwise falls back to a scan+filter.
    """
    try:
        table = _table(PLANTINGS_TABLE)
        # Try GSI query
        try:
            resp = table.query(IndexName="user_id-index", KeyConditionExpression=Key("user_id").eq(str(user_id)))
            items = resp.get("Items", []) or []
            logger.debug("Loaded %d plantings for user %s via GSI", len(items), user_id)
            return items
        except ClientError as e:
            logger.debug("GSI query failed, falling back to scan: %s", e)
        # Fallback scan
        items, start = [], None
        scan_kwargs = {"FilterExpression": Attr("user_id").eq(str(user_id))}
        while True:
            if start:
                scan_kwargs["ExclusiveStartKey"] = start
            resp = table.scan(**scan_kwargs)
            items.extend(resp.get("Items", []) or [])
            start = resp.get("LastEvaluatedKey")
            if not start:
                break
        logger.debug("Scanned and found %d items for user %s", len(items), user_id)
        return items
    except ClientError as e:
        logger.exception("DynamoDB load_user_plantings failed: %s", e)
        return []
    except Exception as e:
        logger.exception("Unexpected error loading plantings: %s", e)
        return []

# -------- Token / request helpers --------
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
        return str(payload.get("sub") or payload.get("username") or payload.get("email") or payload.get("cognito:username") or "")
    except Exception as e:
        logger.debug("JWT parse failed: %s", e)
        return None

def get_user_id_from_request(request) -> Optional[str]:
    # check middleware-attached attributes first
    for attr in ("cognito_payload", "jwt_payload", "cognito_user"):
        payload = getattr(request, attr, None)
        if payload:
            if isinstance(payload, dict):
                user_id = payload.get("sub") or payload.get("username") or payload.get("email")
                if user_id:
                    return str(user_id)
    # Django user
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        try:
            return str(user.pk)
        except Exception:
            return getattr(user, "username", None)
    # Authorization header
    auth = request.META.get("HTTP_AUTHORIZATION") if hasattr(request, "META") else None
    if not auth and hasattr(request, "headers"):
        auth = request.headers.get("Authorization")
    if auth:
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return _extract_userid_from_jwt(parts[1])
    return None

def get_user_id_from_token(token_or_request: Union[str, Any]) -> Optional[str]:
    if isinstance(token_or_request, str):
        return _extract_userid_from_jwt(token_or_request)
    return get_user_id_from_request(token_or_request)