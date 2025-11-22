# tracker/s3_helper.py
import os, logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

S3_BUCKET = os.getenv("S3_BUCKET", "your-bucket-name")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

def upload_planting_image(file_obj, user_id: str, folder: str = "plantings") -> str:
    """
    Uploads Django InMemoryUploadedFile or UploadedFile to S3 and returns a URL.
    file_obj must have .name and .read() or be a File-like object accepted by boto3.upload_fileobj.
    """
    s3 = boto3.client("s3", region_name=AWS_REGION)
    key = f"{folder}/{user_id}/{file_obj.name}"
    try:
        # Use public-read if you want public URLs (or use private + presign)
        s3.upload_fileobj(file_obj, S3_BUCKET, key, ExtraArgs={"ACL": "public-read", "ContentType": getattr(file_obj, "content_type", "binary/octet-stream")})
        url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
        logger.info("Uploaded image to S3: %s", url)
        return url
    except ClientError as e:
        logger.exception("S3 upload failed: %s", e)
        raise