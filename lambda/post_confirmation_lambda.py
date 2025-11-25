import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables - read at runtime, not at module load
DYNAMO_TABLE = os.environ.get("DYNAMO_USERS_TABLE", "")
PK_NAME = os.environ.get("DYNAMO_USERS_PK", "username")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Lazy initialization of DynamoDB - don't initialize at module level
_dynamodb_resource = None
_table_resource = None


def _get_table():
    """Lazy initialization of DynamoDB table - only when needed."""
    global _dynamodb_resource, _table_resource
    
    if not DYNAMO_TABLE:
        return None
    
    if _table_resource is None:
        try:
            _dynamodb_resource = boto3.resource("dynamodb", region_name=AWS_REGION)
            _table_resource = _dynamodb_resource.Table(DYNAMO_TABLE)
            logger.info("Initialized DynamoDB table: %s (PK=%s)", DYNAMO_TABLE, PK_NAME)
        except Exception as e:
            logger.exception("Failed to initialize DynamoDB table: %s", e)
            return None
    
    return _table_resource


def _build_attrs(event):
    """Extract user attributes from Cognito event."""
    attrs = event.get("request", {}).get("userAttributes", {}) or {}
    return {
        "user_id": attrs.get("sub"),
        "email": attrs.get("email"),
        "name": attrs.get("name") or attrs.get("given_name"),
        "preferred_username": attrs.get("preferred_username"),
    }


def lambda_handler(event, context):
    """
    Post Confirmation Lambda trigger for Cognito.
    Saves user data to DynamoDB users table when user confirms account.
    
    IMPORTANT: Always returns the event object - Cognito requires this.
    """
    try:
        logger.info("PostConfirmation trigger for user=%s trigger=%s",
                    event.get("userName"), event.get("triggerSource"))

        # Always return event even if configuration is missing
        if not DYNAMO_TABLE:
            logger.warning("DYNAMO_USERS_TABLE not configured - skipping DynamoDB save")
            return event

        user_name = event.get("userName")
        if not user_name:
            logger.warning("Missing userName in event - skipping DynamoDB save")
            return event

        # Extract attributes
        attrs = _build_attrs(event)
        # Remove None values
        attrs = {k: v for k, v in attrs.items() if v is not None}
        if not attrs:
            logger.info("No attributes to write for user=%s - skipping DynamoDB save", user_name)
            return event

        # Get DynamoDB table (lazy initialization)
        table = _get_table()
        if not table:
            logger.warning("Could not initialize DynamoDB table - skipping save")
            return event

        # Build complete user item with PK (username)
        user_item = {
            PK_NAME: user_name,  # Partition key (required)
        }
        # Add all attributes
        user_item.update(attrs)
        
        # Save to DynamoDB
        try:
            # Use put_item for idempotent upsert (creates if doesn't exist, updates if exists)
            table.put_item(Item=user_item)
            logger.info("✅ DynamoDB put_item succeeded for user=%s (PK=%s), attributes=%s",
                        user_name, PK_NAME, list(attrs.keys()))
        except ClientError as e:
            # Log error but don't fail the signup process
            logger.error("❌ DynamoDB ClientError for user=%s: %s", user_name, str(e))
            # Still return event so Cognito signup succeeds
        except Exception as e:
            # Log error but don't fail the signup process
            logger.error("❌ Unexpected error writing to DynamoDB for user=%s: %s", user_name, str(e))
            # Still return event so Cognito signup succeeds

        # CRITICAL: Always return the event object - Cognito requires this
        return event
        
    except Exception as e:
        # Catch ANY unhandled exception to prevent "Unrecognizable lambda output"
        logger.exception("❌ FATAL ERROR in PostConfirmation Lambda: %s", str(e))
        # Still return event so Cognito signup doesn't fail
        # The signup will succeed even if DynamoDB save fails
        return event