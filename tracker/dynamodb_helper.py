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

# Get DynamoDB table names from settings
DYNAMODB_USERS_TABLE_NAME = getattr(settings, 'DYNAMODB_USERS_TABLE_NAME', 'users')
DYNAMODB_PLANTINGS_TABLE_NAME = getattr(settings, 'DYNAMODB_PLANTINGS_TABLE_NAME', 'plantings')


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


def save_user_to_dynamodb(user_data):
    """
    Save user data to DynamoDB users table.
    
    Args:
        user_data: Dict with user information (must include 'username' or 'sub' as key)
    
    Returns:
        True if successful, False otherwise
    """
    if not user_data:
        logger.error('Cannot save user: user_data is None')
        return False
    
    try:
        # Check AWS credentials first
        if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
            logger.error('AWS credentials not configured! Cannot save user to DynamoDB')
            return False
        
        dynamodb = get_dynamodb_client()
        
        # Use username as the partition key (or sub/email as fallback)
        username = user_data.get('username') or user_data.get('preferred_username') or user_data.get('sub') or user_data.get('email')
        if not username:
            logger.error('Cannot save user: no username/sub/email found in user_data. Available keys: %s', list(user_data.keys()))
            return False
        
        logger.info('Saving user to DynamoDB: username=%s, table=%s', username, DYNAMODB_USERS_TABLE_NAME)
        
        # Prepare user item
        user_item = {
            'username': {'S': str(username)}
        }
        
        # Add other user fields
        if 'sub' in user_data:
            user_item['user_id'] = {'S': str(user_data['sub'])}
        if 'email' in user_data:
            user_item['email'] = {'S': str(user_data['email'])}
        if 'name' in user_data:
            user_item['name'] = {'S': str(user_data['name'])}
        if 'given_name' in user_data:
            user_item['given_name'] = {'S': str(user_data['given_name'])}
        if 'family_name' in user_data:
            user_item['family_name'] = {'S': str(user_data['family_name'])}
        
        # Add login timestamp
        user_item['last_login'] = {'S': datetime.utcnow().isoformat()}
        user_item['created_at'] = {'S': datetime.utcnow().isoformat()}  # Will be updated if user exists
        
        try:
            from botocore.exceptions import ClientError
            
            # Check if table exists first
            try:
                table_info = dynamodb.describe_table(TableName=DYNAMODB_USERS_TABLE_NAME)
                logger.info('Table %s exists. Status: %s', DYNAMODB_USERS_TABLE_NAME, table_info['Table']['TableStatus'])
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'ResourceNotFoundException':
                    logger.error('✗ DynamoDB users table "%s" does not exist!', DYNAMODB_USERS_TABLE_NAME)
                    logger.error('Please create the table in AWS Console or run: python scripts/create_users_table.py')
                    return False
                else:
                    logger.exception('Error checking if table exists: %s', e)
                    return False
            
            # Check if user exists to preserve created_at
            try:
                existing = dynamodb.get_item(
                    TableName=DYNAMODB_USERS_TABLE_NAME,
                    Key={'username': {'S': str(username)}}
                )
                if 'Item' in existing:
                    # User exists, preserve created_at
                    logger.info('User %s already exists, updating last_login', username)
                    if 'created_at' in existing['Item']:
                        user_item['created_at'] = existing['Item']['created_at']
                else:
                    logger.info('Creating new user: %s', username)
            except Exception as check_error:
                logger.warning('Could not check if user exists: %s', check_error)
                # Continue anyway
            
            # Save user
            dynamodb.put_item(
                TableName=DYNAMODB_USERS_TABLE_NAME,
                Item=user_item
            )
            logger.info('✓ Successfully saved user "%s" to DynamoDB users table "%s"', username, DYNAMODB_USERS_TABLE_NAME)
            logger.info('User fields saved: %s', list(user_item.keys()))
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            if error_code == 'ResourceNotFoundException':
                logger.error('✗ DynamoDB users table "%s" does not exist!', DYNAMODB_USERS_TABLE_NAME)
                logger.error('Please create the table in AWS Console')
            elif error_code == 'AccessDeniedException':
                logger.error('✗ Access denied to DynamoDB. Check IAM permissions for: dynamodb:PutItem, dynamodb:GetItem, dynamodb:DescribeTable')
            else:
                logger.exception('DynamoDB ClientError saving user: Code=%s, Message=%s', error_code, error_message)
            return False
        except Exception as db_error:
            logger.exception('DynamoDB put_item failed for user: %s', db_error)
            return False
    except Exception as e:
        logger.exception('Error saving user to DynamoDB: %s', e)
        return False


def save_planting_to_dynamodb(user_id, planting):
    """
    Save a single planting to DynamoDB plantings table.
    
    Args:
        user_id: User's unique identifier (from Cognito 'sub')
        planting: Planting dictionary (must have 'planting_id' or will generate one)
    
    Returns:
        planting_id if successful, None otherwise
    """
    if not user_id:
        logger.error('Cannot save planting: user_id is None')
        return None
    
    try:
        dynamodb = get_dynamodb_client()
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
        
        # Prepare DynamoDB item
        item = {
            'planting_id': {'S': planting_id},
            'user_id': {'S': user_id},
            'crop_name': {'S': str(planting_copy.get('crop_name', ''))},
            'planting_date': {'S': str(planting_copy.get('planting_date', ''))},
            'batch_id': {'S': str(planting_copy.get('batch_id', ''))},
            'notes': {'S': str(planting_copy.get('notes', ''))},
            'plan': {'S': json.dumps(planting_copy.get('plan', []))},
            'image_url': {'S': str(planting_copy.get('image_url', ''))},
            'created_at': {'S': datetime.utcnow().isoformat()},
            'updated_at': {'S': datetime.utcnow().isoformat()}
        }
        
        try:
            from botocore.exceptions import ClientError
            
            # Check if table exists
            try:
                dynamodb.describe_table(TableName=DYNAMODB_PLANTINGS_TABLE_NAME)
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'ResourceNotFoundException':
                    logger.error('DynamoDB plantings table %s does not exist!', DYNAMODB_PLANTINGS_TABLE_NAME)
                    return None
            
            # Save to DynamoDB
            dynamodb.put_item(
                TableName=DYNAMODB_PLANTINGS_TABLE_NAME,
                Item=item
            )
            logger.info('✓ Saved planting %s for user %s to DynamoDB', planting_id, user_id)
            return planting_id
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'ResourceNotFoundException':
                logger.error('DynamoDB plantings table %s does not exist!', DYNAMODB_PLANTINGS_TABLE_NAME)
            else:
                logger.exception('DynamoDB ClientError saving planting: %s', e)
            return None
        except Exception as db_error:
            logger.exception('DynamoDB put_item failed for planting: %s', db_error)
            return None
    except Exception as e:
        logger.exception('Error saving planting to DynamoDB: %s', e)
        return None


def save_user_plantings(user_id, plantings):
    """
    Save multiple plantings to DynamoDB (saves each as separate item).
    
    Args:
        user_id: User's unique identifier (from Cognito 'sub')
        plantings: List of planting dictionaries
    
    Returns:
        True if all successful, False otherwise
    """
    if not user_id:
        logger.error('Cannot save plantings: user_id is None')
        return False
    
    if not plantings:
        logger.warning('No plantings to save for user %s', user_id)
        return True
    
    success_count = 0
    for planting in plantings:
        planting_id = save_planting_to_dynamodb(user_id, planting)
        if planting_id:
            success_count += 1
    
    if success_count == len(plantings):
        logger.info('✓ Saved all %d plantings for user %s to DynamoDB', len(plantings), user_id)
        return True
    else:
        logger.warning('⚠ Saved %d/%d plantings for user %s to DynamoDB', success_count, len(plantings), user_id)
        return success_count > 0


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
        dynamodb = get_dynamodb_client()
        
        # Check if table exists first
        try:
            from botocore.exceptions import ClientError
            try:
                dynamodb.describe_table(TableName=DYNAMODB_PLANTINGS_TABLE_NAME)
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'ResourceNotFoundException':
                    logger.warning('DynamoDB plantings table %s does not exist - returning empty list', DYNAMODB_PLANTINGS_TABLE_NAME)
                else:
                    logger.warning('Error checking DynamoDB table: %s', e)
                return []
        except Exception as e:
            logger.warning('DynamoDB plantings table %s may not exist: %s', DYNAMODB_PLANTINGS_TABLE_NAME, e)
            return []
        
        # Query all plantings for this user
        # Note: This requires a GSI (Global Secondary Index) on user_id, or we scan (less efficient)
        # For now, we'll use scan with filter (works but not optimal for large datasets)
        plantings = []
        try:
            response = dynamodb.scan(
                TableName=DYNAMODB_PLANTINGS_TABLE_NAME,
                FilterExpression='user_id = :user_id',
                ExpressionAttributeValues={
                    ':user_id': {'S': user_id}
                }
            )
            
            for item in response.get('Items', []):
                planting = {
                    'planting_id': item.get('planting_id', {}).get('S', ''),
                    'crop_name': item.get('crop_name', {}).get('S', ''),
                    'planting_date': item.get('planting_date', {}).get('S', ''),
                    'batch_id': item.get('batch_id', {}).get('S', ''),
                    'notes': item.get('notes', {}).get('S', ''),
                    'image_url': item.get('image_url', {}).get('S', ''),
                }
                # Parse plan JSON
                plan_json = item.get('plan', {}).get('S', '[]')
                try:
                    planting['plan'] = json.loads(plan_json)
                except:
                    planting['plan'] = []
                plantings.append(planting)
            
            logger.info('✓ Loaded %d plantings for user %s from DynamoDB plantings table', len(plantings), user_id)
            return plantings
        except Exception as scan_error:
            logger.exception('Error scanning plantings table: %s', scan_error)
            return []
    except Exception as e:
        logger.exception('Error loading plantings from DynamoDB: %s', e)
        return []


def delete_planting_from_dynamodb(planting_id):
    """
    Delete a specific planting by planting_id.
    
    Args:
        planting_id: The planting_id to delete
    
    Returns:
        True if successful, False otherwise
    """
    if not planting_id:
        logger.error('Cannot delete planting: planting_id is None')
        return False
    
    try:
        dynamodb = get_dynamodb_client()
        
        try:
            from botocore.exceptions import ClientError
            
            # Check if table exists
            try:
                dynamodb.describe_table(TableName=DYNAMODB_PLANTINGS_TABLE_NAME)
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'ResourceNotFoundException':
                    logger.error('DynamoDB plantings table %s does not exist!', DYNAMODB_PLANTINGS_TABLE_NAME)
                    return False
            
            # Delete from DynamoDB
            dynamodb.delete_item(
                TableName=DYNAMODB_PLANTINGS_TABLE_NAME,
                Key={
                    'planting_id': {'S': planting_id}
                }
            )
            logger.info('✓ Deleted planting %s from DynamoDB', planting_id)
            return True
        except ClientError as e:
            logger.exception('DynamoDB ClientError deleting planting: %s', e)
            return False
        except Exception as db_error:
            logger.exception('DynamoDB delete_item failed: %s', db_error)
            return False
    except Exception as e:
        logger.exception('Error deleting planting from DynamoDB: %s', e)
        return False


def delete_user_planting(user_id, planting_index):
    """
    Delete a specific planting by index.
    Loads all plantings, finds the one at index, and deletes it by planting_id.
    
    Args:
        user_id: User's unique identifier
        planting_index: Index of planting to delete
    
    Returns:
        True if successful, False otherwise
    """
    plantings = load_user_plantings(user_id)
    if planting_index < len(plantings):
        planting = plantings[planting_index]
        planting_id = planting.get('planting_id')
        if planting_id:
            return delete_planting_from_dynamodb(planting_id)
        else:
            logger.error('Planting at index %d has no planting_id', planting_index)
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

