"""Image storage + processing. Backends: local disk (dev) or S3-compatible object storage (AWS S3, Cloudflare R2, Spaces)."""
from __future__ import annotations

import io
import os
from dataclasses import dataclass

from fastapi import HTTPException
from PIL import Image, ImageOps

from ..config import get_config
from ..utils import new_id

ALLOWED_TYPES = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png"), "WEBP": ("image/webp", "webp")}
SIZES = {"sm": 480, "md": 960, "lg": 1600}


@dataclass
class Stored:
    key: str
    url: str


class LocalStorage:
    def __init__(self):
        cfg = get_config()
        self.root = os.path.abspath(cfg.local_upload_dir)
        self.base_url = cfg.local_media_url.rstrip("/")
        os.makedirs(self.root, exist_ok=True)

    def put(self, key: str, data: bytes, content_type: str) -> Stored:
        path = os.path.join(self.root, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return Stored(key, f"{self.base_url}/{key}")

    def delete(self, key: str) -> None:
        try:
            os.remove(os.path.join(self.root, key))
        except FileNotFoundError:
            pass


class S3Storage:
    def __init__(self):
        import boto3  # lazy: only needed for cloud storage

        cfg = get_config()
        self.cfg = cfg
        self.s3 = boto3.client(
            "s3", region_name=cfg.s3_region, endpoint_url=cfg.s3_endpoint_url or None,
            aws_access_key_id=cfg.s3_access_key_id, aws_secret_access_key=cfg.s3_secret_access_key,
        )

    def put(self, key: str, data: bytes, content_type: str) -> Stored:
        self.s3.put_object(Bucket=self.cfg.s3_bucket, Key=key, Body=data, ContentType=content_type,
                           CacheControl="public, max-age=31536000, immutable")
        return Stored(key, f"{self.cfg.s3_public_base_url.rstrip('/')}/{key}")

    def delete(self, key: str) -> None:
        self.s3.delete_object(Bucket=self.cfg.s3_bucket, Key=key)


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        _storage = S3Storage() if get_config().storage_backend == "s3" else LocalStorage()
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None


def process_image(raw: bytes) -> dict:
    """Validate by actually decoding (not trusting extension/content-type), strip metadata, make webp variants."""
    cfg = get_config()
    if len(raw) > cfg.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Image exceeds {cfg.max_upload_mb} MB")
    try:
        probe = Image.open(io.BytesIO(raw))
        fmt = probe.format
        probe.verify()
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
    except Exception:
        raise HTTPException(415, "File is not a valid image")
    if fmt not in ALLOWED_TYPES:
        raise HTTPException(415, "Only JPEG, PNG and WEBP images are allowed")
    if img.width * img.height > 50_000_000:
        raise HTTPException(413, "Image dimensions too large")
    img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
    variants = {}
    for name, w in SIZES.items():
        im = img.copy()
        if im.width > w:
            im.thumbnail((w, w * 10))
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=82, method=4)
        variants[name] = buf.getvalue()
    return {"width": img.width, "height": img.height, "variants": variants, "format": fmt}


def store_image(raw: bytes, folder: str = "images") -> dict:
    info = process_image(raw)
    st = get_storage()
    base = f"{folder}/{new_id()}"
    out = {"width": info["width"], "height": info["height"], "size": len(raw), "variants": {}, "keys": []}
    for name, data in info["variants"].items():
        s = st.put(f"{base}-{name}.webp", data, "image/webp")
        out["variants"][name] = s.url
        out["keys"].append(s.key)
    out["url"] = out["variants"]["lg"]
    return out


def delete_keys(keys: list[str]) -> None:
    st = get_storage()
    for k in keys:
        try:
            st.delete(k)
        except Exception:
            pass
