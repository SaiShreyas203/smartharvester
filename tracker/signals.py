# tracker/signals.py
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

@receiver(post_save, sender=User)
def sync_user_to_dynamo(sender, instance, created, **kwargs):
    try:
        # lazy import to avoid circular imports
        from .dynamodb_helper import create_or_update_user
        payload = {
            "email": instance.email,
            "first_name": instance.first_name,
            "last_name": instance.last_name,
            "username": instance.username,
        }
        ok = create_or_update_user(user_id=instance.pk, payload=payload)
        if ok:
            logger.info("Synced user %s to Dynamo", instance.pk)
        else:
            logger.warning("Failed to sync user %s to Dynamo", instance.pk)
    except Exception:
        logger.exception("Exception syncing user to Dynamo: %s", instance.pk)

@receiver(post_delete, sender=User)
def delete_user_from_dynamo(sender, instance, **kwargs):
    try:
        from .dynamodb_helper import _table
        table = _table(os.getenv("DYNAMO_USERS_TABLE", "users"))
        table.delete_item(Key={"user_id": str(instance.pk)})
    except Exception:
        logger.exception("Failed deleting user from Dynamo: %s", instance.pk)