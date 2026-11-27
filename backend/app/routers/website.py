"""Website CMS (admin) and the public content API. Draft -> Published -> Archived with preview."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..audit import audit
from ..db import get_db
from ..hotel_settings import get_settings
from ..security import optional_user, public_limiter, require
from ..utils import new_id, paginate, ser, slugify, utcnow
from .common import partial

router = APIRouter(prefix="/website", tags=["website"])

SECTION_KEYS = ["home.hero", "home.intro", "about", "restaurant", "events", "contact", "footer",
                "policy.privacy", "policy.terms", "policy.cancellation"]
ITEM_TYPES = ("facility", "faq", "event", "testimonial")


async def media_map(db, ids: set[str]) -> dict[str, dict]:
    if not ids:
        return {}
    out = {}
    for m in await db.media.find({"_id": {"$in": list(ids)}, "status": "published"}).to_list(None):
        out[m["_id"]] = {"id": m["_id"], "url": m["url"], "variants": m.get("variants", {}), "alt": m.get("alt_text", ""),
                         "width": m.get("width"), "height": m.get("height"), "title": m.get("title", "")}
    return out


def collect_ids(o: Any, acc: set[str]) -> None:
    from ..utils import extract_media_ids

    acc.update(extract_media_ids(o))


def attach_media(o: Any, mm: dict) -> Any:
    """Replace `*media_id(s)` with resolved image objects under `media` / `images` helpers."""
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            out[k] = attach_media(v, mm)
            if (k == "media_id" or k.endswith("_media_id")) and isinstance(v, str):
                out[k.replace("media_id", "image") if k != "media_id" else "image"] = mm.get(v)
            elif (k == "media_ids" or k.endswith("_media_ids")) and isinstance(v, list):
                out[k.replace("media_ids", "images") if k != "media_ids" else "images"] = [mm[i] for i in v if i in mm]
        return out
    if isinstance(o, list):
        return [attach_media(i, mm) for i in o]
    return o


async def resolve(db, payload: Any) -> Any:
    ids: set[str] = set()
    collect_ids(payload, ids)
    return attach_media(payload, await media_map(db, ids))


async def is_preview(preview: bool, user: dict | None) -> bool:
    return bool(preview and user and "website.manage" in user["_perms"])


# ======================= PUBLIC =======================
@router.get("/site", dependencies=[Depends(public_limiter)])
async def site(preview: bool = False, user: dict | None = Depends(optional_user)):
    db = get_db()
    s = await get_settings(db)
    prev = await is_preview(preview, user)
    payload = {
        "published": s["published"] or prev,
        "profile": s["profile"],
        "booking": {k: s["booking"][k] for k in ("currency", "check_in_time", "check_out_time", "min_nights", "max_nights", "max_rooms_per_booking", "booking_rules")},
        "payment": {"allow_pay_at_hotel": s["payment"]["allow_pay_at_hotel"], "require_full_payment": s["payment"]["require_full_payment"],
                    "deposit_enabled": s["payment"]["deposit_enabled"]},
        "cancellation": s["cancellation"],
        "preview": prev,
    }
    sample = await db.room_categories.count_documents({"is_sample": True, "status": "published"})
    payload["has_sample_content"] = sample > 0
    return await resolve(db, payload)


@router.get("/sections/{key}", dependencies=[Depends(public_limiter)])
async def public_section(key: str, preview: bool = False, user: dict | None = Depends(optional_user)):
    db = get_db()
    sec = await db.website_sections.find_one({"key": key})
    prev = await is_preview(preview, user)
    if not sec:
        return {"key": key, "content": None, "status": "missing"}
    if prev:
        return await resolve(db, {"key": key, "content": sec.get("draft"), "status": sec["status"], "preview": True})
    if sec["status"] != "published" or sec.get("published") is None:
        return {"key": key, "content": None, "status": "unpublished"}
    return await resolve(db, {"key": key, "content": sec["published"], "status": "published"})


@router.get("/items/{type_}", dependencies=[Depends(public_limiter)])
async def public_items(type_: str, preview: bool = False, user: dict | None = Depends(optional_user)):
    if type_ not in ITEM_TYPES:
        raise HTTPException(404, "Unknown content type")
    db = get_db()
    q: dict = {"type": type_}
    if not await is_preview(preview, user):
        q["status"] = "published"
    else:
        q["status"] = {"$ne": "archived"}
    items = await db.content_items.find(q).sort([("order", 1), ("created_at", 1)]).to_list(None)
    return await resolve(db, [ser(i) for i in items])


@router.get("/offers", dependencies=[Depends(public_limiter)])
async def public_offers():
    db = get_db()
    today = utcnow().date().isoformat()
    offers = await db.promotions.find({"status": "published", "show_on_website": True}).to_list(None)
    offers = [o for o in offers if (not o.get("valid_to") or o["valid_to"] >= today)]
    out = []
    for o in offers:
        d = ser(o)
        d.pop("code", None) if o.get("hide_code") else None
        out.append(d)
    return await resolve(db, out)


@router.get("/gallery", dependencies=[Depends(public_limiter)])
async def public_gallery():
    items = await get_db().media.find({"status": "published"}).sort([("order", 1), ("created_at", -1)]).to_list(None)
    return [{"id": m["_id"], "url": m["url"], "variants": m.get("variants", {}), "alt": m.get("alt_text", ""), "title": m.get("title", ""),
             "description": m.get("description", ""), "width": m.get("width"), "height": m.get("height")} for m in items]


def _public_category(c: dict) -> dict:
    return ser({k: v for k, v in c.items() if k not in ("created_at", "updated_at", "is_sample_internal")})


@router.get("/rooms", dependencies=[Depends(public_limiter)])
async def public_rooms(preview: bool = False, featured: bool = False, user: dict | None = Depends(optional_user)):
    db = get_db()
    q: dict = {"status": "published"}
    if await is_preview(preview, user):
        q = {"status": {"$ne": "archived"}}
    if featured:
        q["featured"] = True
    cats = await db.room_categories.find(q).sort([("sort_order", 1), ("name", 1)]).to_list(None)
    amenities = {a["_id"]: a for a in await db.amenities.find({}).to_list(None)}
    out = []
    for c in cats:
        d = _public_category(c)
        d["amenities"] = [{"id": a, "name": amenities[a]["name"], "icon": amenities[a].get("icon", "")} for a in c.get("amenity_ids", []) if a in amenities]
        out.append(d)
    return await resolve(db, out)


@router.get("/rooms/{slug}", dependencies=[Depends(public_limiter)])
async def public_room(slug: str, preview: bool = False, user: dict | None = Depends(optional_user)):
    db = get_db()
    c = await db.room_categories.find_one({"slug": slug})
    if not c or (c["status"] != "published" and not (await is_preview(preview, user) and c["status"] != "archived")):
        raise HTTPException(404, "Room not found")
    amenities = {a["_id"]: a for a in await db.amenities.find({}).to_list(None)}
    d = _public_category(c)
    d["amenities"] = [{"id": a, "name": amenities[a]["name"], "icon": amenities[a].get("icon", "")} for a in c.get("amenity_ids", []) if a in amenities]
    return await resolve(db, d)


# ======================= ADMIN CMS =======================
class SectionIn(BaseModel):
    title: str = ""
    content: dict[str, Any] = {}


@router.get("/admin/sections")
async def admin_sections(user: dict = Depends(require("website.manage"))):
    docs = {d["key"]: d for d in await get_db().website_sections.find({}).to_list(None)}
    return [{"key": k, **(ser(docs[k]) if k in docs else {"status": "missing", "title": k, "draft": None, "published": None})} for k in SECTION_KEYS]


@router.put("/admin/sections/{key}")
async def save_section_draft(key: str, body: SectionIn, user: dict = Depends(require("website.manage"))):
    if key not in SECTION_KEYS:
        raise HTTPException(404, "Unknown section")
    db = get_db()
    cur = await db.website_sections.find_one({"key": key})
    status = cur["status"] if cur and cur["status"] == "published" else "draft"
    await db.website_sections.update_one({"key": key}, {"$set": {"title": body.title, "draft": body.content, "status": status, "updated_at": utcnow(), "updated_by": user["name"]},
                                                        "$setOnInsert": {"_id": new_id(), "key": key, "published": None}}, upsert=True)
    await audit(user, "website.section_save", "website_section", key, before=cur and cur.get("draft"), after=body.content)
    return ser(await db.website_sections.find_one({"key": key}))


@router.post("/admin/sections/{key}/publish")
async def publish_section(key: str, user: dict = Depends(require("website.manage"))):
    db = get_db()
    cur = await db.website_sections.find_one({"key": key})
    if not cur or cur.get("draft") is None:
        raise HTTPException(409, "Nothing to publish. Save content first.")
    await db.website_sections.update_one({"key": key}, {"$set": {"published": cur["draft"], "status": "published", "published_at": utcnow()}})
    await audit(user, "website.publish", "website_section", key, after=cur["draft"])
    return ser(await db.website_sections.find_one({"key": key}))


@router.post("/admin/sections/{key}/unpublish")
async def unpublish_section(key: str, archive: bool = False, user: dict = Depends(require("website.manage"))):
    db = get_db()
    r = await db.website_sections.update_one({"key": key}, {"$set": {"status": "archived" if archive else "draft"}})
    if not r.matched_count:
        raise HTTPException(404, "Section not found")
    await audit(user, "website.archive" if archive else "website.unpublish", "website_section", key)
    return ser(await db.website_sections.find_one({"key": key}))


class ItemIn(BaseModel):
    type: Literal["facility", "faq", "event", "testimonial"]
    title: str = Field(default="", max_length=200)
    body: str = Field(default="", max_length=5000)
    question: str = ""
    answer: str = ""
    icon: str = ""
    author: str = ""
    extra: dict[str, Any] = {}
    media_id: str | None = None
    media_ids: list[str] = []
    status: Literal["draft", "published", "archived"] = "draft"
    order: int = 0
    verified: bool = False  # testimonials must be verified/supplied by the hotel


ItemPatch = partial(ItemIn)


@router.get("/admin/items")
async def admin_items(type: str | None = None, user: dict = Depends(require("website.manage"))):
    q = {"type": type} if type else {}
    return [ser(i) for i in await get_db().content_items.find(q).sort([("type", 1), ("order", 1)]).to_list(None)]


@router.post("/admin/items", status_code=201)
async def create_item(body: ItemIn, user: dict = Depends(require("website.manage"))):
    d = {"_id": new_id(), **body.model_dump(), "created_at": utcnow(), "updated_at": utcnow()}
    if d["type"] == "faq" and not (d["question"] and d["answer"]):
        raise HTTPException(422, "FAQs need a question and an answer")
    if d["type"] == "testimonial" and d["status"] == "published" and not d["verified"]:
        raise HTTPException(422, "Only verified testimonials can be published")
    await get_db().content_items.insert_one(d)
    await audit(user, "website.item_create", "content_item", d["_id"], after=d)
    return ser(d)


@router.patch("/admin/items/{iid}")
async def update_item(iid: str, body: ItemPatch, user: dict = Depends(require("website.manage"))):
    db = get_db()
    before = await db.content_items.find_one({"_id": iid})
    if not before:
        raise HTTPException(404, "Item not found")
    patch = body.model_dump(exclude_unset=True)
    merged = {**before, **patch}
    if merged["type"] == "testimonial" and merged["status"] == "published" and not merged.get("verified"):
        raise HTTPException(422, "Only verified testimonials can be published")
    patch["updated_at"] = utcnow()
    await db.content_items.update_one({"_id": iid}, {"$set": patch})
    await audit(user, "website.item_update", "content_item", iid, before=before, after=patch)
    return ser(await db.content_items.find_one({"_id": iid}))


@router.delete("/admin/items/{iid}")
async def delete_item(iid: str, user: dict = Depends(require("website.manage"))):
    r = await get_db().content_items.delete_one({"_id": iid})
    if not r.deleted_count:
        raise HTTPException(404, "Item not found")
    await audit(user, "website.item_delete", "content_item", iid)
    return {"ok": True}
