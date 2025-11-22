"""
S3 helper functions for uploading and managing user images.
"""
import boto3
import uuid
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def get_s3_client():
    """Get S3 client with AWS credentials."""
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
    )


def upload_planting_image(image_file, user_id):
    """
    Upload planting image to S3.
    Images are stored at: media/planting_images/{uuid}.{ext}
    
    Args:
        image_file: Django UploadedFile object
        user_id: User's unique identifier (from Cognito 'sub') - used for logging only
    
    Returns:
        Image URL string if successful, empty string if failed
    """
    if not image_file or not image_file.name:
        return ""
    
    try:
        s3 = get_s3_client()
        extension = image_file.name.split('.')[-1].lower()
        
        # Generate unique UUID for filename
        # Images stored at: media/planting_images/{uuid}.{ext}
        image_uuid = uuid.uuid4()
        key = f"media/planting_images/{image_uuid}.{extension}"
        
        # Upload to S3
        s3.upload_fileobj(
            image_file,
            settings.AWS_STORAGE_BUCKET_NAME,
            key
        )
        
        # Construct public URL matching actual S3 structure
        # Format: https://terratrack-media.s3.amazonaws.com/media/planting_images/{uuid}.{ext}
        image_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{key}"
        logger.info('✓ Uploaded image to S3: %s (user: %s)', key, user_id)
        return image_url
        
    except Exception as e:
        logger.exception('Error uploading image to S3: %s', e)
        return ""


def get_user_images(user_id):
    """
    List all images from S3 (all users).
    Note: Since images are stored by UUID only, we list all images.
    In production, you might want to track image ownership in DynamoDB.
    
    Args:
        user_id: User's unique identifier (not used for filtering, kept for API compatibility)
    
    Returns:
        List of image URLs
    """
    try:
        s3 = get_s3_client()
        prefix = "media/planting_images/"
        
        response = s3.list_objects_v2(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Prefix=prefix
        )
        
        image_urls = []
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                # Only include actual image files (not directories)
                if key.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    image_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{key}"
                    image_urls.append(image_url)
        
        logger.info('Found %d images in S3 (prefix: %s)', len(image_urls), prefix)
        return image_urls
        
    except Exception as e:
        logger.exception('Error listing images from S3: %s', e)
        return []


def delete_image_from_s3(image_url):
    """
    Delete an image from S3 given its URL.
    
    Args:
        image_url: Full S3 URL of the image
        Format: https://terratrack-media.s3.amazonaws.com/media/planting_images/{uuid}.{ext}
    
    Returns:
        True if successful, False otherwise
    """
    if not image_url:
        return False
    
    try:
        s3 = get_s3_client()
        # Extract key from URL
        # URL format: https://bucket.s3.amazonaws.com/media/planting_images/{uuid}.{ext}
        if '.s3.amazonaws.com/' in image_url:
            key = image_url.split('.s3.amazonaws.com/')[1]
        elif 's3://' in image_url:
            # Handle s3:// URL format
            key = image_url.split('s3://')[1].split('/', 1)[1] if '/' in image_url.split('s3://')[1] else ''
        else:
            logger.error('Invalid S3 URL format: %s', image_url)
            return False
        
        if not key:
            logger.error('Could not extract key from URL: %s', image_url)
            return False
        
        s3.delete_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=key
        )
        logger.info('✓ Deleted image from S3: %s', key)
        return True
        
    except Exception as e:
        logger.exception('Error deleting image from S3: %s', e)
        return False

