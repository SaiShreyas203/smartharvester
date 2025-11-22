import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

User = get_user_model()

@receiver(post_save, sender=User)
def sync_user_to_dynamo(sender, instance, created, **kwargs):
    """Signal handler: Sync Django User to DynamoDB when created or updated."""
    try:
        from tracker.dynamodb_helper import create_or_update_user
        
        # Use Django user ID as user_id for DynamoDB
        user_id = str(instance.pk)
        
        payload = {
            "email": instance.email or "",
            "first_name": instance.first_name or "",
            "last_name": instance.last_name or "",
            "username": instance.username,
        }
        
        # Add name if available
        if instance.first_name or instance.last_name:
            payload["name"] = f"{instance.first_name} {instance.last_name}".strip()
        
        logger.info("Signal: Syncing user %s (pk=%s) to DynamoDB (created=%s)", 
                   instance.username, instance.pk, created)
        
        ok = create_or_update_user(user_id=user_id, payload=payload)
        if not ok:
            logger.error("✗ DynamoDB write returned False for user %s (pk=%s)", instance.username, instance.pk)
        else:
            logger.info("✓ DynamoDB write succeeded for user %s (pk=%s)", instance.username, instance.pk)
    except Exception as exc:
        logger.exception("✗ Failed to sync user %s to DynamoDB: %s", instance.pk, exc)
        # Don't raise - signal handlers should not break the save operation

@receiver(post_delete, sender=User)
def delete_user_from_dynamo(sender, instance, **kwargs):
    """Signal handler: Delete Django User from DynamoDB when deleted."""
    try:
        from tracker.dynamodb_helper import delete_user
        
        user_id = str(instance.pk)
        logger.info("Signal: Deleting user %s (pk=%s) from DynamoDB", instance.username, instance.pk)
        
        ok = delete_user(user_id=user_id)
        if not ok:
            logger.error("✗ DynamoDB delete returned False for user %s (pk=%s)", instance.username, instance.pk)
        else:
            logger.info("✓ DynamoDB delete succeeded for user %s (pk=%s)", instance.username, instance.pk)
    except Exception as exc:
        logger.exception("✗ Failed to delete user %s from DynamoDB: %s", instance.pk, exc)
        # Don't raise - signal handlers should not break the delete operation