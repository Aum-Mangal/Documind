"""S3-compatible object storage: SeaweedFS locally, Cloudflare R2 in production."""
from functools import lru_cache

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings


@lru_cache
def get_s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 3},
        ),
    )


def ensure_bucket() -> None:
    bucket = get_settings().s3_bucket
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") not in ("404", "NoSuchBucket", "NotFound"):
            raise
        client.create_bucket(Bucket=bucket)


def check() -> None:
    get_s3_client().head_bucket(Bucket=get_settings().s3_bucket)


def put_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    get_s3_client().put_object(Bucket=get_settings().s3_bucket, Key=key, Body=data, ContentType=content_type)


def get_object(key: str) -> bytes:
    return get_s3_client().get_object(Bucket=get_settings().s3_bucket, Key=key)["Body"].read()


def delete_object(key: str) -> None:
    get_s3_client().delete_object(Bucket=get_settings().s3_bucket, Key=key)
