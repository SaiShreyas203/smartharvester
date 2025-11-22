import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from . import dynamo

logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(post_save, sender=User)
def sync_user_to_dynamo(sender, instance, created, **kwargs):
    """
    After a User is created/updated, write a corresponding item to the DynamoDB users table.
    Non-blocking: log errors but do not raise so signup is not interrupted.
    """
    try:
        payload = {
            "email": instance.email,
            "first_name": instance.first_name,
            "last_name": instance.last_name,
            "username": instance.username,
        }
        ok = dynamo.create_or_update_user(user_id=instance.pk, payload=payload)
        if ok:
            logger.info("Dynamo sync succeeded for user %s", instance.pk)
        else:
            logger.error("Dynamo sync returned False for user %s", instance.pk)
    except Exception as exc:
        logger.exception("Exception syncing user %s to Dynamo: %s", instance.pk, exc)


@receiver(post_delete, sender=User)
def delete_user_from_dynamo(sender, instance, **kwargs):
    try:
        ok = dynamo.delete_user(user_id=instance.pk)
        if ok:
            logger.info("Dynamo delete succeeded for user %s", instance.pk)
        else:
            logger.error("Dynamo delete returned False for user %s", instance.pk)
    except Exception:
        logger.exception("Exception deleting user %s from Dynamo", instance.pk)