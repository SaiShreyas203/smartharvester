import logging
from typing import Optional, Dict, Any

import boto3
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


def _sns_client():
    # Use settings.AWS_REGION if set, otherwise default boto3 will use env/instance profile
    region = getattr(settings, "AWS_REGION", None)
    return boto3.client("sns", region_name=region) if region else boto3.client("sns")


def get_topic_arn() -> Optional[str]:
    # Prefer settings then environment; set this in config/settings.py or as env var
    return getattr(settings, "SNS_TOPIC_ARN", None)


def publish_notification(subject: str, message: str, topic_arn: Optional[str] = None, message_attributes: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
    """
    Publish a message to the harvest SNS topic.
    Returns the boto3 response dict on success, or None on failure.
    """
    arn = topic_arn or get_topic_arn()
    if not arn:
        logger.error("publish_notification: no SNS topic ARN configured")
        return None
    client = _sns_client()
    kwargs = {"TopicArn": arn, "Message": message}
    if subject:
        kwargs["Subject"] = subject
    if message_attributes:
        kwargs["MessageAttributes"] = message_attributes
    try:
        resp = client.publish(**kwargs)
        logger.info("Published SNS message to %s MessageId=%s", arn, resp.get("MessageId"))
        return resp
    except ClientError as e:
        logger.exception("SNS publish failed: %s", e)
        return None
    except Exception:
        logger.exception("Unexpected error publishing SNS message")
        return None


def subscribe_email_to_topic(email: str, topic_arn: Optional[str] = None) -> Optional[str]:
    """
    Subscribe an email endpoint to the topic. Returns the SubscriptionArn or None.
    For 'email' protocol, subscription must be confirmed by the recipient (they will get a confirmation email).
    """
    arn = topic_arn or get_topic_arn()
    if not arn:
        logger.error("subscribe_email_to_topic: no SNS topic ARN configured")
        return None
    client = _sns_client()
    try:
        resp = client.subscribe(TopicArn=arn, Protocol="email", Endpoint=email, ReturnSubscriptionArn=True)
        sub_arn = resp.get("SubscriptionArn")
        logger.info("Subscribed %s to %s (SubscriptionArn=%s). Email must confirm subscription.", email, arn, sub_arn)
        return sub_arn
    except ClientError as e:
        logger.exception("SNS subscribe failed: %s", e)
        return None
    except Exception:
        logger.exception("Unexpected error subscribing to SNS")
        return None


def list_subscriptions_for_topic(topic_arn: Optional[str] = None):
    arn = topic_arn or get_topic_arn()
    if not arn:
        logger.error("list_subscriptions_for_topic: no SNS topic ARN configured")
        return []
    client = _sns_client()
    try:
        resp = client.list_subscriptions_by_topic(TopicArn=arn)
        return resp.get("Subscriptions", [])
    except ClientError as e:
        logger.exception("SNS list_subscriptions_by_topic failed: %s", e)
        return []
    except Exception:
        logger.exception("Unexpected error listing subscriptions")
        return []