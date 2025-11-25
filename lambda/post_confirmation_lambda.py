import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

USERS_TABLE = os.environ.get("USERS_TABLE") or os.environ.get("DYNAMO_USERS_TABLE", "")
USERS_PK = os.environ.get("USERS_PK") or os.environ.get("DYNAMO_USERS_PK", "username")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

if not USERS_TABLE:
    logger.warning("USERS_TABLE not set in env; handler will skip DynamoDB save")

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
users_table = dynamodb.Table(USERS_TABLE) if USERS_TABLE else None


def lambda_handler(event, context):
    try:
        user_name = event.get("userName")
        if not user_name:
            return event

        if not users_table:
            return event

        attrs = event.get("request", {}).get("userAttributes", {}) or {}
        
        user_item = {
            USERS_PK: user_name,
            "user_id": attrs.get("sub"),
            "email": attrs.get("email"),
            "name": attrs.get("name") or attrs.get("given_name"),
            "preferred_username": attrs.get("preferred_username"),
        }
        
        user_item = {k: v for k, v in user_item.items() if v is not None}

        try:
            users_table.put_item(Item=user_item)
            logger.info("Saved user to DynamoDB: username=%s", user_name)
        except ClientError:
            logger.exception("DynamoDB put_item failed for user=%s", user_name)

        return event
    except Exception:
        logger.exception("Error in PostConfirmation Lambda")
        return event