import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from tracker.models import Planting
from tracker import dynamo

logger = logging.getLogger(__name__)

User = get_user_model()

@receiver(post_save, sender=User)
def sync_user_to_dynamo(sender, instance, created, **kwargs):
    try:
        payload = {
            "email": instance.email,
            "first_name": instance.first_name,
            "last_name": instance.last_name,
            "username": instance.username,
        }
        ok = dynamo.create_or_update_user(user_id=instance.pk, payload=payload)
        if not ok:
            logger.error("Dynamo write returned False for user %s", instance.pk)
        else:
            logger.info("Dynamo write succeeded for user %s", instance.pk)
    except Exception as exc:
        logger.exception("Failed to sync user %s to DynamoDB: %s", instance.pk, exc)

@receiver(post_delete, sender=User)
def delete_user_from_dynamo(sender, instance, **kwargs):
    try:
        ok = dynamo.delete_user(user_id=instance.pk)
        if not ok:
            logger.error("Dynamo delete returned False for user %s", instance.pk)
        else:
            logger.info("Dynamo delete succeeded for user %s", instance.pk)
    except Exception:
        logger.exception("Failed to delete user %s from DynamoDB", instance.pk)

@receiver(post_save, sender=Planting)
def sync_planting_to_dynamo(sender, instance, created, **kwargs):
    try:
        payload = {
            "user_id": str(instance.user_id) if instance.user_id else None,
            "crop_name": instance.crop_name,
            "planting_date": instance.planting_date.isoformat() if instance.planting_date else None,
            "harvest_date": instance.harvest_date.isoformat() if instance.harvest_date else None,
            "notes": instance.notes,
            "batch_id": getattr(instance, "batch_id", None),
        }
        ok = dynamo.create_or_update_planting(planting_id=instance.pk, payload=payload)
        if not ok:
            logger.error("Dynamo write returned False for planting %s", instance.pk)
        else:
            logger.info("Dynamo write succeeded for planting %s", instance.pk)
    except Exception:
        logger.exception("Failed to sync planting %s to DynamoDB", instance.pk)

@receiver(post_delete, sender=Planting)
def delete_planting_from_dynamo(sender, instance, **kwargs):
    try:
        ok = dynamo.delete_planting(planting_id=instance.pk)
        if not ok:
            logger.error("Dynamo delete returned False for planting %s", instance.pk)
        else:
            logger.info("Dynamo delete succeeded for planting %s", instance.pk)
    except Exception:
        logger.exception("Failed to delete planting %s from DynamoDB", instance.pk)