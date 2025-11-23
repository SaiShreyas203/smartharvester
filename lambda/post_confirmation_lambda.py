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

def _build_item(event):
    user_name = event.get("userName")
    attrs = event.get("request", {}).get("userAttributes", {}) or {}

    item = {
        PK_NAME: user_name,
        "user_id": attrs.get("sub"),
        "email": attrs.get("email"),
        "name": attrs.get("name") or attrs.get("given_name"),
        "preferred_username": attrs.get("preferred_username")
    }

    return {k: v for k, v in item.items() if v is not None}

def lambda_handler(event, context):
    logger.info("Received event for user confirmation: %s", {k: event.get(k) for k in ("userName", "triggerSource")})
    if not DYNAMO_TABLE:
        logger.error("DYNAMO_USERS_TABLE not configured")
        return event

    item = _build_item(event)
    if not item:
        logger.warning("No user attributes to persist: %s", event)
        return event

    try:
        table.put_item(
            Item=item,
            ConditionExpression=f"attribute_not_exists({PK_NAME})"
        )
        logger.info("Created user item in DynamoDB: %s", item.get(PK_NAME))
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code == "ConditionalCheckFailedException":
            logger.info("User item already exists: %s", item.get(PK_NAME))
        else:
            logger.exception("DynamoDB put_item failed")
    except Exception:
        logger.exception("Unexpected error writing to DynamoDB")

    return event