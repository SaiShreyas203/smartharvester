"""
DynamoDB helper functions for storing and retrieving user plantings.
"""
import os
import json
import logging
from decimal import Decimal
from datetime import date, datetime
from botocore.exceptions import ClientError
import boto3

logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DYNAMO_USERS_TABLE = os.getenv("DYNAMO_USERS_TABLE", "users")
DYNAMO_PLANTINGS_TABLE = os.getenv("DYNAMO_PLANTINGS_TABLE", "plantings")

_dynamo = None


def dynamo_resource():
    """Get or create DynamoDB resource (singleton)."""
    global _dynamo
    if _dynamo is None:
        # Check for AWS credentials from Django settings or environment
        try:
            from django.conf import settings
            access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
            secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
            
            if access_key and secret_key:
                _dynamo = boto3.resource(
                    "dynamodb",
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name=AWS_REGION
                )
                logger.info("DynamoDB resource created with explicit credentials")
            else:
                # Use default credentials (from environment or IAM role)
                _dynamo = boto3.resource("dynamodb", region_name=AWS_REGION)
                logger.info("DynamoDB resource created with default credentials")
        except Exception as e:
            logger.exception("Error creating DynamoDB resource: %s", e)
            # Fallback to default
            _dynamo = boto3.resource("dynamodb", region_name=AWS_REGION)
    return _dynamo


def _to_dynamo_numbers(obj):
    """Converts floats/decimals to Decimal for DynamoDB compatibility."""
    if isinstance(obj, dict):
        return {k: _to_dynamo_numbers(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_to_dynamo_numbers(v) for v in obj]
    if isinstance(obj, float):
        return Decimal(str(obj))
    return obj


def create_or_update_user(user_id: str, payload: dict) -> bool:
    """
    Create or update a user item in DynamoDB.
    Note: Table uses 'username' as partition key (not user_id).
    payload: dictionary of attributes to store (email, first_name, username, ...).
    Must include 'username' in payload for partition key.
    """
    try:
        table = dynamo_resource().Table(DYNAMO_USERS_TABLE)
        
        # Table uses 'username' as partition key, so username must be in payload
        username = payload.get("username")
        if not username:
            # If no username in payload, use user_id as username (fallback)
            username = str(user_id)
            payload["username"] = username
            logger.warning("No username in payload, using user_id as username: %s", username)
        
        # Partition key is username, but we also store user_id for reference
        item = {"username": str(username)}
        if user_id and str(user_id) != str(username):
            item["user_id"] = str(user_id)
        item.update(payload)
        item = _to_dynamo_numbers(item)
        
        logger.info("Attempting to save user to DynamoDB: username=%s, user_id=%s, table=%s", 
                   username, user_id, DYNAMO_USERS_TABLE)
        logger.debug("Item to save: %s", item)
        
        table.put_item(Item=item)
        logger.info("✓✓✓ SUCCESS: Saved user to DynamoDB: username=%s, user_id=%s", username, user_id)
        return True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        logger.error("✗✗✗ DynamoDB put_item (user) failed: Code=%s, Message=%s", error_code, error_message)
        logger.exception("Full error details:")
        return False
    except Exception as e:
        logger.exception("✗✗✗ Unexpected error saving user to DynamoDB: %s", e)
        return False


def delete_user(user_id: str) -> bool:
    """
    Delete a user from DynamoDB.
    Note: Table uses 'username' as partition key, so we need to find user by user_id first.
    """
    table = dynamo_resource().Table(DYNAMO_USERS_TABLE)
    try:
        # Since partition key is username, we need to scan to find by user_id
        # Or if we have username, use it directly
        # For now, try to find by user_id attribute
        response = table.scan(
            FilterExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': str(user_id)}
        )
        
        if response.get('Items'):
            # Found user, delete by username (partition key)
            username = response['Items'][0].get('username')
            if username:
                table.delete_item(Key={"username": str(username)})
                logger.info("✓ Deleted user from DynamoDB: username=%s, user_id=%s", username, user_id)
                return True
        
        logger.warning("User with user_id=%s not found in DynamoDB", user_id)
        return False
    except ClientError as e:
        logger.exception("DynamoDB delete_item (user) failed: %s", e)
        return False


def create_or_update_planting(planting_id: str, payload: dict) -> bool:
    """
    Create or update a planting item in DynamoDB.
    Partition key: planting_id (string)
    payload should include user_id, crop_name, planting_date, harvest_date, notes, batch_id, etc.
    """
    table = dynamo_resource().Table(DYNAMO_PLANTINGS_TABLE)
    item = {"planting_id": str(planting_id)}
    item.update(payload)
    item = _to_dynamo_numbers(item)
    try:
        table.put_item(Item=item)
        return True
    except ClientError as e:
        logger.exception("DynamoDB put_item (planting) failed: %s", e)
        return False


def delete_planting(planting_id: str) -> bool:
    """Delete a planting from DynamoDB."""
    table = dynamo_resource().Table(DYNAMO_PLANTINGS_TABLE)
    try:
        table.delete_item(Key={"planting_id": str(planting_id)})
        return True
    except ClientError as e:
        logger.exception("DynamoDB delete_item (planting) failed: %s", e)
        return False


# ============================================================================
# Helper functions for Cognito token extraction (still needed by views)
# ============================================================================

def get_user_id_from_token(request):
    """
    Extract user identifier from Cognito ID token.
    Returns 'sub' (user's unique identifier) or email as fallback.
    """
    try:
        id_token = request.session.get('id_token') or request.session.get('cognito_tokens', {}).get('id_token')
        if not id_token:
            logger.debug('No ID token found in session')
            return None
        
        from jose import jwt
        payload = jwt.decode(id_token, options={"verify_signature": False})
        user_id = payload.get('sub')
        if not user_id:
            user_id = payload.get('email')
        
        if user_id:
            logger.debug('Extracted user_id: %s from token', user_id)
        else:
            logger.warning('No user_id found in token payload. Available keys: %s', list(payload.keys()))
        
        return user_id
    except Exception as e:
        logger.exception('Error extracting user ID from token: %s', e)
        return None


def get_user_data_from_token(request):
    """
    Extract user data from Cognito ID token.
    Returns dict with user information (sub, email, username, etc.)
    """
    try:
        id_token = request.session.get('id_token') or request.session.get('cognito_tokens', {}).get('id_token')
        if not id_token:
            return None
        
        from jose import jwt
        payload = jwt.decode(id_token, options={"verify_signature": False})
        return payload
    except Exception as e:
        logger.exception('Error extracting user data from token: %s', e)
        return None


# ============================================================================
# Compatibility functions for existing views (wrappers around new functions)
# ============================================================================

def save_user_to_dynamodb(user_data):
    """
    Save user data to DynamoDB users table.
    Compatibility wrapper around create_or_update_user.
    
    Args:
        user_data: Dict with user information (must include 'sub' or 'user_id' as key)
    
    Returns:
        True if successful, False otherwise
    """
    if not user_data:
        logger.error('Cannot save user: user_data is None')
        return False
    
    # Extract user_id from user_data
    user_id = user_data.get('sub') or user_data.get('user_id') or user_data.get('username')
    if not user_id:
        logger.error('Cannot save user: no user_id/sub/username found in user_data')
        return False
    
    # Prepare payload (exclude user_id as it's the partition key)
    payload = {}
    if 'email' in user_data:
        payload['email'] = str(user_data['email'])
    if 'name' in user_data:
        payload['name'] = str(user_data['name'])
    if 'given_name' in user_data:
        payload['given_name'] = str(user_data['given_name'])
    if 'family_name' in user_data:
        payload['family_name'] = str(user_data['family_name'])
    if 'username' in user_data:
        payload['username'] = str(user_data['username'])
    
    # Add timestamps
    payload['last_login'] = datetime.utcnow().isoformat()
    payload['created_at'] = datetime.utcnow().isoformat()
    
    # Ensure username is in payload (required for partition key)
    if 'username' not in payload and 'username' in user_data:
        payload['username'] = str(user_data['username'])
    elif 'username' not in payload:
        # Use user_id as username if no username provided
        payload['username'] = str(user_id)
    
    username = payload['username']
    
    # Check if user exists to preserve created_at (by username since it's the partition key)
    try:
        table = dynamo_resource().Table(DYNAMO_USERS_TABLE)
        existing = table.get_item(Key={"username": str(username)})
        if 'Item' in existing:
            logger.info('User %s already exists, updating last_login', username)
            if 'created_at' in existing['Item']:
                payload['created_at'] = existing['Item']['created_at']
            if 'notifications_enabled' in existing['Item']:
                payload['notifications_enabled'] = existing['Item']['notifications_enabled']
        else:
            logger.info('Creating new user: %s', username)
            payload['notifications_enabled'] = True  # Default to enabled
    except Exception as check_error:
        logger.warning('Could not check if user exists: %s', check_error)
        payload['notifications_enabled'] = True  # Default to enabled
    
    return create_or_update_user(user_id, payload)


def save_planting_to_dynamodb(user_id, planting):
    """
    Save a single planting to DynamoDB plantings table.
    Compatibility wrapper around create_or_update_planting.
    
    Args:
        user_id: User's unique identifier (from Cognito 'sub')
        planting: Planting dictionary (must have 'planting_id' or will generate one)
    
    Returns:
        planting_id if successful, None otherwise
    """
    if not user_id:
        logger.error('Cannot save planting: user_id is None')
        return None
    
    import uuid
    
    # Generate planting_id if not present
    planting_id = planting.get('planting_id')
    if not planting_id:
        planting_id = str(uuid.uuid4())
        planting['planting_id'] = planting_id
    
    # Convert date objects to ISO strings
    planting_copy = planting.copy()
    if isinstance(planting_copy.get('planting_date'), date):
        planting_copy['planting_date'] = planting_copy['planting_date'].isoformat()
    # Ensure plan tasks have string dates
    for task in planting_copy.get('plan', []):
        if 'due_date' in task and isinstance(task.get('due_date'), date):
            task['due_date'] = task['due_date'].isoformat()
    
    # Prepare payload
    payload = {
        'user_id': str(user_id),
        'crop_name': str(planting_copy.get('crop_name', '')),
        'planting_date': str(planting_copy.get('planting_date', '')),
        'batch_id': str(planting_copy.get('batch_id', '')),
        'notes': str(planting_copy.get('notes', '')),
        'plan': json.dumps(planting_copy.get('plan', [])),
        'image_url': str(planting_copy.get('image_url', '')),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    # Check if planting exists to preserve created_at
    try:
        table = dynamo_resource().Table(DYNAMO_PLANTINGS_TABLE)
        existing = table.get_item(Key={"planting_id": planting_id})
        if 'Item' in existing:
            logger.info('Planting %s already exists, updating', planting_id)
            if 'created_at' in existing['Item']:
                payload['created_at'] = existing['Item']['created_at']
        else:
            payload['created_at'] = datetime.utcnow().isoformat()
    except Exception:
        payload['created_at'] = datetime.utcnow().isoformat()
    
    success = create_or_update_planting(planting_id, payload)
    if success:
        logger.info('✓ Saved planting %s for user %s to DynamoDB', planting_id, user_id)
        return planting_id
    return None


def load_user_plantings(user_id):
    """
    Load all plantings for a user from DynamoDB plantings table.
    
    Args:
        user_id: User's unique identifier (from Cognito 'sub')
    
    Returns:
        List of planting dictionaries, or empty list if not found or error
    """
    if not user_id:
        logger.warning('Cannot load plantings: user_id is None')
        return []
    
    try:
        table = dynamo_resource().Table(DYNAMO_PLANTINGS_TABLE)
        
        # Scan table with filter for user_id
        # Note: For better performance, consider adding a GSI on user_id
        response = table.scan(
            FilterExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': str(user_id)}
        )
        
        plantings = []
        for item in response.get('Items', []):
            planting = {
                'planting_id': item.get('planting_id', ''),
                'crop_name': item.get('crop_name', ''),
                'planting_date': item.get('planting_date', ''),
                'batch_id': item.get('batch_id', ''),
                'notes': item.get('notes', ''),
                'image_url': item.get('image_url', ''),
            }
            
            # Parse plan JSON
            plan_str = item.get('plan', '[]')
            try:
                planting['plan'] = json.loads(plan_str) if isinstance(plan_str, str) else plan_str
            except:
                planting['plan'] = []
            
            plantings.append(planting)
        
        logger.info('✓ Loaded %d plantings for user %s from DynamoDB plantings table', len(plantings), user_id)
        return plantings
        
    except Exception as e:
        logger.exception('Error loading plantings from DynamoDB: %s', e)
        return []


def delete_planting_from_dynamodb(planting_id):
    """
    Delete a specific planting by planting_id.
    Compatibility wrapper around delete_planting.
    
    Args:
        planting_id: The planting_id to delete
    
    Returns:
        True if successful, False otherwise
    """
    if not planting_id:
        logger.error('Cannot delete planting: planting_id is None')
        return False
    
    success = delete_planting(planting_id)
    if success:
        logger.info('✓ Deleted planting %s from DynamoDB', planting_id)
    return success


def get_user_notification_preference(username):
    """
    Get user's notification preference from DynamoDB.
    
    Args:
        username: User's username (used to look up user_id)
    
    Returns:
        Boolean indicating if notifications are enabled (defaults to True)
    """
    try:
        # Try to find user by username
        table = dynamo_resource().Table(DYNAMO_USERS_TABLE)
        # Scan for username (not ideal, but works if username is stored)
        response = table.scan(
            FilterExpression='username = :username',
            ExpressionAttributeValues={':username': str(username)}
        )
        
        if response.get('Items'):
            item = response['Items'][0]
            notifications_enabled = item.get('notifications_enabled', True)
            return notifications_enabled
        
        return True  # Default to enabled
    except Exception as e:
        logger.exception('Error getting notification preference for %s: %s', username, e)
        return True  # Default to enabled


def update_user_notification_preference(username, enabled):
    """
    Update user's notification preference in DynamoDB.
    
    Args:
        username: User's username (used to look up user_id)
        enabled: Boolean indicating if notifications should be enabled
    
    Returns:
        True if successful, False otherwise
    """
    try:
        table = dynamo_resource().Table(DYNAMO_USERS_TABLE)
        
        # Find user by username
        response = table.scan(
            FilterExpression='username = :username',
            ExpressionAttributeValues={':username': str(username)}
        )
        
        if response.get('Items'):
            user_item = response['Items'][0]
            user_id = user_item.get('user_id')
            
            # Update notification preference
            table.update_item(
                Key={"user_id": user_id},
                UpdateExpression='SET notifications_enabled = :enabled',
                ExpressionAttributeValues={
                    ':enabled': enabled
                }
            )
            logger.info('✓ Updated notification preference for %s: %s', username, enabled)
            return True
        else:
            logger.warning('User %s not found in DynamoDB', username)
            return False
            
    except Exception as e:
        logger.exception('Error updating notification preference for %s: %s', username, e)
        return False


# ============================================================================
# Compatibility for management command
# ============================================================================

def get_dynamodb_client():
    """
    Get DynamoDB client (for compatibility with management command).
    Note: New code should use dynamo_resource() instead.
    """
    from django.conf import settings
    access_key = settings.AWS_ACCESS_KEY_ID
    secret_key = settings.AWS_SECRET_ACCESS_KEY
    region = getattr(settings, 'AWS_S3_REGION_NAME', AWS_REGION)
    
    return boto3.client(
        'dynamodb',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )


# For backward compatibility
DYNAMODB_USERS_TABLE_NAME = DYNAMO_USERS_TABLE
DYNAMODB_PLANTINGS_TABLE_NAME = DYNAMO_PLANTINGS_TABLE
