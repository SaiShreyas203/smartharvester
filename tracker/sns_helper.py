"""
SNS helper functions for sending notifications to users.
"""
import boto3
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def get_sns_client():
    """Get SNS client with AWS credentials."""
    access_key = settings.AWS_ACCESS_KEY_ID
    secret_key = settings.AWS_SECRET_ACCESS_KEY
    region = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
    
    if not access_key or not secret_key:
        logger.warning('AWS credentials not fully configured for SNS')
    
    return boto3.client(
        'sns',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )


def subscribe_email_to_topic(email, topic_arn=None):
    """
    Subscribe an email address to an SNS topic.
    
    Args:
        email: Email address to subscribe
        topic_arn: SNS topic ARN (defaults to settings.SNS_TOPIC_ARN)
    
    Returns:
        subscription_arn if successful, None otherwise
    """
    try:
        if not topic_arn:
            topic_arn = getattr(settings, 'SNS_TOPIC_ARN', None)
        
        if not topic_arn:
            logger.error('SNS_TOPIC_ARN not configured in settings')
            return None
        
        sns = get_sns_client()
        
        logger.info('Subscribing email %s to topic %s', email, topic_arn)
        response = sns.subscribe(
            TopicArn=topic_arn,
            Protocol='email',
            Endpoint=email
        )
        
        subscription_arn = response.get('SubscriptionArn')
        logger.info('✓ Email %s subscribed. Subscription ARN: %s', email, subscription_arn)
        return subscription_arn
        
    except Exception as e:
        logger.exception('Error subscribing email %s to SNS topic: %s', email, e)
        return None


def send_notification(email, subject, message, topic_arn=None):
    """
    Send a notification to a user via SNS (email).
    
    Args:
        email: User's email address
        subject: Email subject
        message: Email message body
        topic_arn: SNS topic ARN (defaults to settings.SNS_TOPIC_ARN)
    
    Returns:
        MessageId if successful, None otherwise
    """
    try:
        if not topic_arn:
            topic_arn = getattr(settings, 'SNS_TOPIC_ARN', None)
        
        if not topic_arn:
            logger.error('SNS_TOPIC_ARN not configured in settings')
            return None
        
        sns = get_sns_client()
        
        logger.info('Sending notification to %s via topic %s', email, topic_arn)
        logger.info('Subject: %s', subject)
        
        # For email notifications via SNS, we need to ensure the email is subscribed
        # SNS will send to all subscribers, so we include email in message for filtering
        full_message = f"{message}\n\n---\nThis notification is for: {email}"
        
        response = sns.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=full_message
        )
        
        message_id = response.get('MessageId')
        logger.info('✓ Notification sent. Message ID: %s', message_id)
        return message_id
        
    except Exception as e:
        logger.exception('Error sending notification to %s: %s', email, e)
        return None


def send_harvest_reminder(email, planting_info):
    """
    Send a harvest reminder notification for a specific planting.
    
    Args:
        email: User's email address
        planting_info: Dict with planting details (crop_name, planting_date, due_date, etc.)
    
    Returns:
        MessageId if successful, None otherwise
    """
    crop_name = planting_info.get('crop_name', 'your crop')
    due_date = planting_info.get('due_date', 'soon')
    
    subject = f"🌱 Harvest Reminder: {crop_name} needs attention"
    message = f"""Hello!

This is a reminder that your {crop_name} planting needs attention.

Planting Date: {planting_info.get('planting_date', 'N/A')}
Due Date: {due_date}

Remember to check your planting care plan for all scheduled tasks.

Happy harvesting!
- TerraTrack Team
"""
    
    return send_notification(email, subject, message)

