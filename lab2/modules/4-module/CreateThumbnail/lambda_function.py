import logging
import os
import uuid
from urllib.parse import unquote_plus

import boto3
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3")


def _destination_bucket(source_bucket: str) -> str:
    explicit = os.environ.get("DEST_BUCKET", "").strip()
    if explicit:
        return explicit
    return f"{source_bucket}-resized"


def _resize_image(src_path: str, dst_path: str) -> None:
    _, ext = os.path.splitext(dst_path)
    ext = ext.lower()
    with Image.open(src_path) as im:
        w, h = im.size
        im.thumbnail((max(1, w // 2), max(1, h // 2)))
        save_kw: dict = {}
        if ext in (".jpg", ".jpeg"):
            rgb = im.convert("RGB")
            rgb.save(dst_path, quality=85, optimize=True)
            return
        if ext == ".webp":
            save_kw["quality"] = 85
        im.save(dst_path, **save_kw)


def lambda_handler(event, context):
    for record in event.get("Records", []):
        download_path = None
        upload_path = None
        try:
            bucket = record["s3"]["bucket"]["name"]
            key = unquote_plus(record["s3"]["object"]["key"])
        except (KeyError, TypeError) as exc:
            logger.warning("Skipping malformed S3 record: %s", exc)
            continue

        if not key or key.endswith("/"):
            logger.info("Skipping empty or folder key: %r", key)
            continue

        dest_bucket = _destination_bucket(bucket)
        base = os.path.basename(key)
        _, suffix = os.path.splitext(base)
        if not suffix:
            suffix = ".img"

        uid = uuid.uuid4().hex
        download_path = f"/tmp/in-{uid}{suffix}"
        upload_path = f"/tmp/out-{uid}{suffix}"

        try:
            s3_client.download_file(bucket, key, download_path)
            _resize_image(download_path, upload_path)
            dest_key = f"resized-{key}"
            s3_client.upload_file(upload_path, dest_bucket, dest_key)
            logger.info("Uploaded s3://%s/%s", dest_bucket, dest_key)
        except UnidentifiedImageError:
            logger.warning("Not a supported image, skipping: s3://%s/%s", bucket, key)
        except Exception:
            logger.exception("Failed processing s3://%s/%s", bucket, key)
            raise
        finally:
            for path in (download_path, upload_path):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    return {"statusCode": 200}
