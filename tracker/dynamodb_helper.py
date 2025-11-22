"""
DynamoDB helper functions for storing and retrieving user plantings.
"""
import boto3
import json
from datetime import date, datetime
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Initialize DynamoDB client
def get_dynamodb_client():
    """Get DynamoDB client with AWS credentials."""
    return boto3.client(
        'dynamodb',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
    )

# Get DynamoDB table name from settings
DYNAMODB_TABLE_NAME = getattr(settings, 'DYNAMODB_PLANTINGS_TABLE_NAME', 'user_plantings')


def get_user_id_from_token(request):
    """
    Extract user identifier from Cognito ID token.
    Returns 'sub' (user's unique identifier) or email as fallback.
    """
    try:
        id_token = request.session.get('id_token') or request.session.get('cognito_tokens', {}).get('id_token')
        if not id_token:
            return None
        
        # Decode token without verification (we just need the user ID)
        from jose import jwt
        # Decode without verification to get user ID
        # Using decode with verify_signature=False to avoid needing JWKS
        payload = jwt.decode(id_token, options={"verify_signature": False})
        # Use 'sub' (subject) as the unique user identifier
        user_id = payload.get('sub')
        if not user_id:
            # Fallback to email if sub is not available
            user_id = payload.get('email')
        return user_id
    except Exception as e:
        logger.error('Error extracting user ID from token: %s', e)
        return None


def save_user_plantings(user_id, plantings):
    """
    Save user plantings to DynamoDB.
    
    Args:
        user_id: User's unique identifier (from Cognito 'sub')
        plantings: List of planting dictionaries
    
    Returns:
        True if successful, False otherwise
    """
    if not user_id:
        logger.error('Cannot save plantings: user_id is None')
        return False
    
    try:
        dynamodb = get_dynamodb_client()
        
        # Convert date objects to ISO strings for JSON serialization
        plantings_json = []
        for planting in plantings:
            planting_copy = planting.copy()
            # Ensure planting_date is a string
            if isinstance(planting_copy.get('planting_date'), date):
                planting_copy['planting_date'] = planting_copy['planting_date'].isoformat()
            # Ensure plan tasks have string dates
            for task in planting_copy.get('plan', []):
                if 'due_date' in task and isinstance(task.get('due_date'), date):
                    task['due_date'] = task['due_date'].isoformat()
            plantings_json.append(planting_copy)
        
        # Save to DynamoDB
        dynamodb.put_item(
            TableName=DYNAMODB_TABLE_NAME,
            Item={
                'user_id': {'S': user_id},  # Partition key
                'plantings': {'S': json.dumps(plantings_json)},  # Store as JSON string
                'updated_at': {'S': datetime.utcnow().isoformat()}
            }
        )
        logger.info('Saved %d plantings for user %s to DynamoDB', len(plantings), user_id)
        return True
    except Exception as e:
        logger.exception('Error saving plantings to DynamoDB: %s', e)
        return False


def load_user_plantings(user_id):
    """
    Load user plantings from DynamoDB.
    
    Args:
        user_id: User's unique identifier (from Cognito 'sub')
    
    Returns:
        List of planting dictionaries, or empty list if not found or error
    """
    if not user_id:
        logger.warning('Cannot load plantings: user_id is None')
        return []
    
    try:
        dynamodb = get_dynamodb_client()
        
        response = dynamodb.get_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'user_id': {'S': user_id}
            }
        )
        
        if 'Item' in response:
            plantings_json = response['Item'].get('plantings', {}).get('S', '[]')
            plantings = json.loads(plantings_json)
            logger.info('Loaded %d plantings for user %s from DynamoDB', len(plantings), user_id)
            return plantings
        else:
            logger.info('No plantings found for user %s in DynamoDB', user_id)
            return []
    except Exception as e:
        logger.exception('Error loading plantings from DynamoDB: %s', e)
        return []


def delete_user_planting(user_id, planting_index):
    """
    Delete a specific planting by index.
    Note: This loads all plantings, removes the one at index, and saves back.
    
    Args:
        user_id: User's unique identifier
        planting_index: Index of planting to delete
    
    Returns:
        True if successful, False otherwise
    """
    plantings = load_user_plantings(user_id)
    if planting_index < len(plantings):
        del plantings[planting_index]
        return save_user_plantings(user_id, plantings)
    return False

