import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DYNAMO_TABLE = os.environ.get("DYNAMO_USERS_TABLE", "")
PK_NAME = os.environ.get("DYNAMO_USERS_PK", "username")

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DYNAMO_TABLE)


def _build_attrs(event):
    attrs = event.get("request", {}).get("userAttributes", {}) or {}
    return {
        "user_id": attrs.get("sub"),
        "email": attrs.get("email"),
        "name": attrs.get("name") or attrs.get("given_name"),
        "preferred_username": attrs.get("preferred_username"),
    }


def lambda_handler(event, context):
    logger.info("PostConfirmation trigger for user=%s trigger=%s",
                event.get("userName"), event.get("triggerSource"))

    if not DYNAMO_TABLE:
        logger.error("DYNAMO_USERS_TABLE not configured")
        return event

    user_name = event.get("userName")
    if not user_name:
        logger.error("Missing userName in event")
        return event

    attrs = _build_attrs(event)
    # remove None values
    attrs = {k: v for k, v in attrs.items() if v is not None}
    if not attrs:
        logger.info("No attributes to write for user=%s", user_name)
        return event

    # Build complete user item with PK (username)
    user_item = {
        PK_NAME: user_name,  # Partition key (required)
    }
    # Add all attributes
    user_item.update(attrs)
    
    try:
        # Use put_item for idempotent upsert (creates if doesn't exist, updates if exists)
        # This ensures user is always saved, even if Lambda runs multiple times
        table.put_item(Item=user_item)
        logger.info("DynamoDB put_item succeeded for user=%s (PK=%s), attributes=%s",
                    user_name, PK_NAME, list(attrs.keys()))
    except ClientError as e:
        logger.exception("DynamoDB put_item failed for user=%s", user_name)
    except Exception:
        logger.exception("Unexpected error writing to DynamoDB for user=%s", user_name)

    return event