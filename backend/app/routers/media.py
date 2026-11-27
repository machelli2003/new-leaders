"""Central media library. Files in object storage; metadata and references are stored in MongoDB."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..audit import audit
from ..config import get_config
from ..db import get_db
from ..security import require
from ..services import storage
from ..utils import extract_media_ids, new_id, paginate, ser, utcnow

router = APIRouter(prefix="/media", tags=["media"])
Category = Literal["logo", "banner", "room", "facility", "restaurant", "event", "gallery", "promotion", "other"]
USAGE_SOURCES = [("hotel_settings", "Hotel profile", lambda d: "Hotel profile / banners"),
                 ("room_categories", "Room category", lambda d: d.get("name", "")),
                 ("rooms", "Room", lambda d: f"Room {d.get('number', '')}"),
                 ("website_sections", "Website section", lambda d: d.get("title") or d.get("key", "")),
                 ("content_items", "Website content", lambda d: f"{d.get('type', '')}: {d.get('title') or d.get('question') or ''}"),
                 ("promotions", "Offer", lambda d: d.get("title", ""))]


async def _read_upload(file: UploadFile) -> bytes:
    limit = get_config().max_upload_mb * 1024 * 1024
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(413, f"Image exceeds {get_config().max_upload_mb} MB")
    return raw


async def usage_of(db, media_id: str) -> list[dict]:
    out = []
    for coll, label, namer in USAGE_SOURCES:
        for d in await db[coll].find({}).to_list(None):
            if media_id in extract_media_ids(d):
                out.append({"collection": coll, "type": label, "id": d["_id"], "name": namer(d)})
    return out


class MediaPatch(BaseModel):
    title: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    alt_text: str | None = Field(default=None, max_length=250)
    category: Category | None = None
    status: Literal["draft", "published"] | None = None
    order: int | None = None


@router.get("")
async def list_media(q: str | None = None, category: str | None = None, status: str | None = None, page: int = 1,
                     page_size: int = 40, user: dict = Depends(require("media.manage", "rooms.manage", "website.manage", any_of=True))):
    query: dict = {}
    if category:
        query["category"] = category
    if status:
        query["status"] = status
    if q:
        query["$or"] = [{"title": {"$regex": q, "$options": "i"}}, {"description": {"$regex": q, "$options": "i"}},
                        {"alt_text": {"$regex": q, "$options": "i"}}]
    return await paginate(get_db().media, query, [("order", 1), ("created_at", -1)], page, page_size)


@router.post("", status_code=201)
async def upload(files: list[UploadFile] = File(...), category: Category = Form("other"), title: str = Form(""),
                 alt_text: str = Form(""), status: Literal["draft", "published"] = Form("published"),
                 user: dict = Depends(require("media.manage"))):
    if len(files) > 20:
        raise HTTPException(413, "Upload at most 20 images at a time")
    db = get_db()
    created = []
    for f in files:
        raw = await _read_upload(f)
        info = storage.store_image(raw)
        name = (f.filename or "image").rsplit(".", 1)[0][:100]
        doc = {"_id": new_id(), "title": title or name, "description": "", "alt_text": alt_text or title or name, "category": category,
               "status": status, "order": 0, "url": info["url"], "variants": info["variants"], "width": info["width"], "height": info["height"],
               "size": info["size"], "storage_keys": info["keys"], "uploaded_by": user["_id"], "created_at": utcnow(), "updated_at": utcnow()}
        await db.media.insert_one(doc)
        created.append(doc)
        await audit(user, "media.upload", "media", doc["_id"], after={"title": doc["title"], "category": category})
    return [ser(d) for d in created]


@router.get("/{mid}")
async def get_media(mid: str, user: dict = Depends(require("media.manage", "rooms.manage", "website.manage", any_of=True))):
    m = await get_db().media.find_one({"_id": mid})
    if not m:
        raise HTTPException(404, "Image not found")
    return {**ser(m), "usage": await usage_of(get_db(), mid)}


@router.patch("/{mid}")
async def update_media(mid: str, body: MediaPatch, user: dict = Depends(require("media.manage"))):
    db = get_db()
    patch = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    patch["updated_at"] = utcnow()
    r = await db.media.update_one({"_id": mid}, {"$set": patch})
    if not r.matched_count:
        raise HTTPException(404, "Image not found")
    return ser(await db.media.find_one({"_id": mid}))


@router.post("/{mid}/replace")
async def replace_media(mid: str, file: UploadFile = File(...), user: dict = Depends(require("media.manage"))):
    db = get_db()
    m = await db.media.find_one({"_id": mid})
    if not m:
        raise HTTPException(404, "Image not found")
    info = storage.store_image(await _read_upload(file))  # same media id, so every place using it updates automatically
    storage.delete_keys(m.get("storage_keys", []))
    await db.media.update_one({"_id": mid}, {"$set": {"url": info["url"], "variants": info["variants"], "width": info["width"], "height": info["height"],
                                                      "size": info["size"], "storage_keys": info["keys"], "updated_at": utcnow()}})
    await audit(user, "media.replace", "media", mid)
    return ser(await db.media.find_one({"_id": mid}))


@router.get("/{mid}/usage")
async def media_usage(mid: str, user: dict = Depends(require("media.manage", "website.manage", "rooms.manage", any_of=True))):
    return await usage_of(get_db(), mid)


@router.delete("/{mid}")
async def delete_media(mid: str, force: bool = False, user: dict = Depends(require("media.manage"))):
    db = get_db()
    m = await db.media.find_one({"_id": mid})
    if not m:
        raise HTTPException(404, "Image not found")
    used = await usage_of(db, mid)
    if used and not force:
        raise HTTPException(409, {"message": "This image is in use. Deleting it will leave blank images in those places.", "usage": used})
    await db.media.delete_one({"_id": mid})
    storage.delete_keys(m.get("storage_keys", []))
    await audit(user, "media.delete", "media", mid, before={"title": m["title"], "used_in": len(used)})
    return {"ok": True, "was_used_in": len(used)}
