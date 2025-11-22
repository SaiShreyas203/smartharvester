"""
Simple S3 helpers for uploading and deleting planting images.

- upload_planting_image(file_obj, user_id, folder="plantings") -> returns public URL (or presigned URL if you prefer)
- delete_image_from_s3(url) -> deletes object by deriving key from the url (best-effort)

Configure S3_BUCKET and AWS_REGION via environment variables.
"""
import os
import logging
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

S3_BUCKET = os.getenv("S3_BUCKET", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
# Use public-read by default; change if your bucket policy requires private objects + presigned urls.
DEFAULT_EXTRA_ARGS = {"ACL": "public-read"}


def _s3_client():
    return boto3.client("s3", region_name=AWS_REGION)


def upload_planting_image(file_obj, user_id: str, folder: str = "plantings") -> str:
    """
    Upload Django UploadedFile to S3 and return a URL.
    file_obj should be the request.FILES['image'] object (has .name and .file).
    """
    if not S3_BUCKET:
        raise RuntimeError("S3_BUCKET not configured in environment")

    s3 = _s3_client()
    # sanitize name minimally
    filename = getattr(file_obj, "name", "upload")
    key = f"{folder}/{user_id}/{filename}"
    try:
        # file_obj may be InMemoryUploadedFile or TemporaryUploadedFile; upload_fileobj works for both
        s3.upload_fileobj(file_obj, S3_BUCKET, key, ExtraArgs=DEFAULT_EXTRA_ARGS | {"ContentType": getattr(file_obj, "content_type", "binary/octet-stream")} if isinstance(DEFAULT_EXTRA_ARGS, dict) else DEFAULT_EXTRA_ARGS)
    except TypeError:
        # On some Python versions dict union is not supported; fallback:
        try:
            extra = DEFAULT_EXTRA_ARGS.copy()
            extra["ContentType"] = getattr(file_obj, "content_type", "binary/octet-stream")
            s3.upload_fileobj(file_obj, S3_BUCKET, key, ExtraArgs=extra)
        except Exception as e:
            logger.exception("S3 upload failed: %s", e)
            raise
    except Exception as e:
        logger.exception("S3 upload failed: %s", e)
        raise

    # Return public URL format for region-aware S3
    url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
    logger.info("Uploaded file to S3: %s", url)
    return url


def delete_image_from_s3(url: str) -> bool:
    """
    Remove object from S3 given a url previously returned by upload_planting_image.
    Performs a best-effort extraction of the key from the URL.
    """
    if not url:
        return False
    if not S3_BUCKET:
        logger.warning("S3_BUCKET not configured; cannot delete %s", url)
        return False
    try:
        parsed = urlparse(url)
        # path starts with /bucket/key or /key depending on URL style
        key = parsed.path.lstrip("/")
        # If URL includes bucket prefix, remove it
        if key.startswith(f"{S3_BUCKET}/"):
            key = key[len(f"{S3_BUCKET}/"):]
        s3 = _s3_client()
        s3.delete_object(Bucket=S3_BUCKET, Key=key)
        logger.info("Deleted S3 object %s/%s", S3_BUCKET, key)
        return True
    except ClientError as e:
        logger.exception("Failed deleting S3 object %s: %s", url, e)
        return False
    except Exception as e:
        logger.exception("Failed deleting S3 object %s: %s", url, e)
        return False