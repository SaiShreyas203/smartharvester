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

    # Use update_item to upsert/merge attributes (won't overwrite PK)
    update_expressions = []
    expr_attr_values = {}
    expr_attr_names = {}

    for i, (k, v) in enumerate(attrs.items()):
        name_key = f"#k{i}"
        val_key = f":v{i}"
        expr_attr_names[name_key] = k
        expr_attr_values[val_key] = v
        update_expressions.append(f"{name_key} = {val_key}")

    update_expr = "SET " + ", ".join(update_expressions)

    try:
        response = table.update_item(
            Key={PK_NAME: user_name},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
            ReturnValues="ALL_NEW"
        )
        logger.info("DynamoDB update succeeded for user=%s, attributes=%s",
                    user_name, list(attrs.keys()))
        # response['Attributes'] contains the up-to-date item
    except ClientError as e:
        logger.exception("DynamoDB update_item failed for user=%s", user_name)
    except Exception:
        logger.exception("Unexpected error writing to DynamoDB for user=%s", user_name)

    return event