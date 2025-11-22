import os
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DYNAMO_USERS_TABLE = os.getenv("DYNAMO_USERS_TABLE", "users")
DYNAMO_PLANTINGS_TABLE = os.getenv("DYNAMO_PLANTINGS_TABLE", "plantings")

_resource = None


def dynamo_resource():
    global _resource
    if _resource is None:
        _resource = boto3.resource("dynamodb", region_name=AWS_REGION)
    return _resource


def _to_decimal(obj: Any) -> Any:
    """
    Convert floats in the payload to Decimal for DynamoDB compatibility.
    Recurses through lists/dicts.
    """
    if isinstance(obj, dict):
        return {k: _to_decimal(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_to_decimal(v) for v in obj]
    if isinstance(obj, float):
        return Decimal(str(obj))
    return obj


def create_or_update_user(user_id: str, payload: Dict[str, Any]) -> bool:
    """
    Put or overwrite a user item in the users table.
    Partition key expected: "user_id" (string). Adjust if your table uses a different key name.
    """
    table_name = DYNAMO_USERS_TABLE
    table = dynamo_resource().Table(table_name)
    item = {"user_id": str(user_id)}
    item.update(payload)
    item = _to_decimal(item)
    try:
        table.put_item(Item=item)
        logger.info("Wrote user %s to DynamoDB table %s", user_id, table_name)
        return True
    except ClientError as e:
        logger.exception("Failed to put user %s into DynamoDB: %s", user_id, e)
        return False


def delete_user(user_id: str) -> bool:
    table_name = DYNAMO_USERS_TABLE
    table = dynamo_resource().Table(table_name)
    try:
        table.delete_item(Key={"user_id": str(user_id)})
        logger.info("Deleted user %s from DynamoDB table %s", user_id, table_name)
        return True
    except ClientError as e:
        logger.exception("Failed to delete user %s from DynamoDB: %s", user_id, e)
        return False