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
            logger.debug('No ID token found in session')
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
        
        if user_id:
            logger.debug('Extracted user_id: %s from token', user_id)
        else:
            logger.warning('No user_id found in token payload. Available keys: %s', list(payload.keys()))
        
        return user_id
    except Exception as e:
        logger.exception('Error extracting user ID from token: %s', e)
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
        try:
            from botocore.exceptions import ClientError
            
            # First check if table exists
            try:
                dynamodb.describe_table(TableName=DYNAMODB_TABLE_NAME)
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'ResourceNotFoundException':
                    logger.error('DynamoDB table %s does not exist!', DYNAMODB_TABLE_NAME)
                    logger.error('Please run: python scripts/create_dynamodb_table.py')
                    return False
                else:
                    logger.warning('Could not check if table exists: %s', e)
            except Exception as describe_error:
                logger.warning('Could not check if table exists: %s', describe_error)
            
            # Save to DynamoDB
            dynamodb.put_item(
                TableName=DYNAMODB_TABLE_NAME,
                Item={
                    'user_id': {'S': user_id},  # Partition key
                    'plantings': {'S': json.dumps(plantings_json)},  # Store as JSON string
                    'updated_at': {'S': datetime.utcnow().isoformat()}
                }
            )
            logger.info('✓ Saved %d plantings for user %s to DynamoDB table %s', len(plantings), user_id, DYNAMODB_TABLE_NAME)
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'ResourceNotFoundException':
                logger.error('DynamoDB table %s does not exist!', DYNAMODB_TABLE_NAME)
                logger.error('Please run: python scripts/create_dynamodb_table.py')
            else:
                logger.exception('DynamoDB ClientError for user %s: %s', user_id, e)
            return False
        except Exception as db_error:
            logger.exception('DynamoDB put_item failed for user %s: %s', user_id, db_error)
            return False
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
        
        # Check if table exists first
        try:
            from botocore.exceptions import ClientError
            try:
                dynamodb.describe_table(TableName=DYNAMODB_TABLE_NAME)
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'ResourceNotFoundException':
                    logger.warning('DynamoDB table %s does not exist - returning empty list', DYNAMODB_TABLE_NAME)
                else:
                    logger.warning('Error checking DynamoDB table: %s', e)
                return []
        except Exception as e:
            logger.warning('DynamoDB table %s may not exist: %s', DYNAMODB_TABLE_NAME, e)
            return []
        
        response = dynamodb.get_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={
                'user_id': {'S': user_id}
            }
        )
        
        if 'Item' in response:
            plantings_json = response['Item'].get('plantings', {}).get('S', '[]')
            plantings = json.loads(plantings_json)
            logger.info('✓ Loaded %d plantings for user %s from DynamoDB table %s', len(plantings), user_id, DYNAMODB_TABLE_NAME)
            return plantings
        else:
            logger.info('No plantings found for user %s in DynamoDB table %s', user_id, DYNAMODB_TABLE_NAME)
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


def migrate_session_to_dynamodb(user_id, session_plantings):
    """
    Migrate plantings from session to DynamoDB (one-time migration).
    
    Args:
        user_id: User's unique identifier
        session_plantings: List of plantings from session
    
    Returns:
        True if successful, False otherwise
    """
    if not user_id or not session_plantings:
        return False
    
    try:
        # Check if user already has data in DynamoDB
        existing = load_user_plantings(user_id)
        if existing:
            logger.info('User %s already has data in DynamoDB, skipping migration', user_id)
            return True
        
        # Save session data to DynamoDB
        logger.info('Migrating %d plantings from session to DynamoDB for user %s', len(session_plantings), user_id)
        return save_user_plantings(user_id, session_plantings)
    except Exception as e:
        logger.exception('Error migrating session data to DynamoDB: %s', e)
        return False

