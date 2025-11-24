import os
import uuid
import logging
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_S3_REGION_NAME", "us-east-1"))

USERS_TABLE = os.getenv("DYNAMODB_USERS_TABLE_NAME", "users")
PLANTINGS_TABLE = os.getenv("DYNAMODB_PLANTINGS_TABLE_NAME", "user_plantings")

_dynamo_resource = None


def _resource():
    global _dynamo_resource
    if _dynamo_resource is None:
        _dynamo_resource = boto3.resource("dynamodb", region_name=AWS_REGION)
    return _dynamo_resource


def get_users_table():
    return _resource().Table(USERS_TABLE)


def get_plantings_table():
    return _resource().Table(PLANTINGS_TABLE)


# --- Users helpers ---
def get_user(username):
    try:
        resp = get_users_table().get_item(Key={"username": username})
        return resp.get("Item")
    except ClientError:
        logger.exception("DynamoDB get_user failed for %s", username)
        return None


def put_user(user_item):
    if "username" not in user_item:
        raise ValueError("user_item must include 'username'")
    try:
        get_users_table().put_item(Item=user_item)
        return True
    except ClientError:
        logger.exception("DynamoDB put_user failed for %s", user_item.get("username"))
        return False


def list_users(limit=100, exclusive_start_key=None):
    kwargs = {}
    if limit:
        kwargs["Limit"] = limit
    if exclusive_start_key:
        kwargs["ExclusiveStartKey"] = exclusive_start_key
    try:
        resp = get_users_table().scan(**kwargs)
        return resp.get("Items", []), resp.get("LastEvaluatedKey")
    except ClientError:
        logger.exception("DynamoDB scan users failed")
        return [], None


# --- Plantings helpers ---
def create_planting(username, planting_data):
    planting_id = planting_data.get("planting_id") or str(uuid.uuid4())
    item = {
        "username": username,
        "planting_id": planting_id,
        **planting_data,
    }
    try:
        get_plantings_table().put_item(Item=item)
        return item
    except ClientError:
        logger.exception("DynamoDB put planting failed for %s/%s", username, planting_id)
        return None


def get_plantings_for_user(username):
    try:
        resp = get_plantings_table().query(KeyConditionExpression=Key("username").eq(username))
        return resp.get("Items", [])
    except ClientError:
        logger.exception("DynamoDB query plantings failed for %s", username)
        return []


def get_planting(username, planting_id):
    try:
        resp = get_plantings_table().get_item(Key={"username": username, "planting_id": planting_id})
        return resp.get("Item")
    except ClientError:
        logger.exception("DynamoDB get planting failed for %s/%s", username, planting_id)
        return None


def update_planting(username, planting_id, updates: dict):
    if not updates:
        return None
    expression_parts = []
    expression_vals = {}
    for i, (k, v) in enumerate(updates.items()):
        placeholder = f":v{i}"
        expression_parts.append(f"{k} = {placeholder}")
        expression_vals[placeholder] = v
    update_expr = "SET " + ", ".join(expression_parts)
    try:
        resp = get_plantings_table().update_item(
            Key={"username": username, "planting_id": planting_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expression_vals,
            ReturnValues="ALL_NEW",
        )
        return resp.get("Attributes")
    except ClientError:
        logger.exception("DynamoDB update planting failed for %s/%s", username, planting_id)
        return None


def delete_planting(username, planting_id):
    try:
        get_plantings_table().delete_item(Key={"username": username, "planting_id": planting_id})
        return True
    except ClientError:
        logger.exception("DynamoDB delete planting failed for %s/%s", username, planting_id)
        return False