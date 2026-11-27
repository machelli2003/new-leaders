"""Import verified hotel details and image references from the official website.

Run from backend/: python -m scripts.seed_real_data [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import db as database
from app.config import get_config
from app.utils import new_id, utcnow

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "scratch_images.json"
SITE_URL = "https://newleadershotelandeventcentre.com/"
MENU_URL = (
    "https://img1.wsimg.com/blobby/go/"
    "bfd7518b-95bf-49de-83a5-1a42796015bc/TAFO%20DESCRIPT.pdf"
)
BOOKING_URL = "https://forms.gle/k9XNSg3otVWHUYDA6"
EVENTS_URL = "https://thewordeventscentre.com/"
MAPS_URL = (
    "https://www.google.com/maps/dir//6.246155,-0.3811928/"
    "@6.2461187,-0.3817592,308m/data=!3m1!1e3"
)
FACILITY_IMAGE_TITLES = {
    "On-site restaurant": "Restaurant dining area",
    "Rooftop bar and lounge": "Hotel bar counter",
    "Events centre": "Event hall",
    "24/7 front desk": "Hotel reception area",
    "Conference room (up to 100 guests)": "Conference room setup",
}


def load_manifest() -> dict:
    if not MANIFEST.exists():
        raise FileNotFoundError(f"Image manifest not found: {MANIFEST}. Run scrape_images.py first.")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("source_url") != SITE_URL or not manifest.get("images"):
        raise ValueError(f"Image manifest is empty or is not for {SITE_URL}")
    return manifest


def make_profile(image_ids: dict[str, str]) -> dict:
    logo_id = image_ids.get("logo.png")
    banner_ids = [
        image_id for filename, image_id in image_ids.items()
        if filename in ("official-video-poster", "DJI_20240725161443_0022_D-d11f1e9.jpg")
    ]
    return {
        "name": "New Leaders Hotel and Events Centre",
        "branch_name": "Akyem Tafo Branch",
        "description": (
            "Hotel accommodation, local dining and an events centre at Tontro Junction, "
            "Akyem Tafo, in Ghana's Eastern Region. The official website describes "
            "comfortable rooms with modern conveniences and city views."
        ),
        "address": "Tontro Junction",
        "town": "Akyem Tafo",
        "region": "Eastern Region",
        "country": "Ghana",
        "latitude": 6.245934,
        "longitude": -0.381074,
        "phones": ["0598616671", "0248498755"],
        "emails": [],
        "website_domain": "newleadershotelandeventcentre.com",
        "socials": {
            "facebook": "https://www.facebook.com/share/1B55DiJg8M/",
            "instagram": "",
            "x": "https://www.x.com/hotel_lead54391",
            "tiktok": "",
            "youtube": "https://www.youtube.com/watch?v=e9jZyCXB-6I",
            "whatsapp": "https://wa.me/233598616671",
        },
        "logo_media_id": logo_id,
        "banner_media_ids": banner_ids,
        "source_url": SITE_URL,
    }


def make_sections(
    image_ids: dict[str, str],
    event_media_ids: list[str] | None = None,
    restaurant_media_ids: list[str] | None = None,
) -> list[dict]:
    hero_id = image_ids.get("DJI_20240725161443_0022_D-d11f1e9.jpg")
    intro_id = image_ids.get("DJI_20240725161443_0022_D-d11f1e9.jpg")
    return [
        {
            "key": "home.hero",
            "title": "Homepage banner",
            "content": {
                "headline": "A warm welcome in Akyem Tafo",
                "subheadline": (
                    "Comfortable rooms, local dining and an events offering from "
                    "New Leaders Hotel and Events Centre."
                ),
                "cta_label": "Book Now",
                "banner_media_ids": [hero_id] if hero_id else [],
            },
        },
        {
            "key": "home.intro",
            "title": "Homepage introduction",
            "content": {
                "title": "Welcome to New Leaders Hotel and Events Centre",
                "body": (
                    "The hotel offers accommodation for solo and group travellers, "
                    "with comfortable mattresses, modern conveniences and city views."
                ),
                "media_id": intro_id,
            },
        },
        {
            "key": "about",
            "title": "About the hotel",
            "content": {
                "title": "About New Leaders Hotel and Events Centre",
                "body": (
                    "New Leaders Hotel and Events Centre brings accommodation, dining "
                    "and event facilities together at Tontro Junction in Akyem Tafo, "
                    "in Ghana's Eastern Region. The hotel welcomes individual and "
                    "group travellers; its website describes rooms with comfortable "
                    "mattresses, modern conveniences and city views.\n\n"
                    "Guests can enjoy local cuisine at the on-site restaurant and "
                    "unwind at the rooftop bar and lounge. The events venue has a "
                    "conference room with seating for up to 100 guests, with enquiries "
                    "welcomed for conferences, business meetings, seminars, workshops "
                    "and private celebrations. Contact the venue to confirm availability "
                    "and arrangements.\n\n"
                    "The business also lists an Amasaman branch in Ga-West, Accra. "
                    "The front desk is listed as open 24/7. Contact the relevant branch "
                    "for reservations, restaurant information or event enquiries."
                ),
                "media_id": intro_id,
                "highlights": [
                    {
                        "title": "Accommodation",
                        "text": "A welcoming option for solo and group travellers, with rooms described as having comfortable mattresses, modern conveniences and city views.",
                    },
                    {
                        "title": "Dining & rooftop lounge",
                        "text": "Enjoy local cuisine at the on-site restaurant and relax at the rooftop bar and lounge.",
                    },
                    {
                        "title": "Meetings & celebrations",
                        "text": "The conference room seats up to 100 guests. Enquire about conferences, meetings, seminars, workshops and private celebrations.",
                    },
                    {
                        "title": "Akyem Tafo branch",
                        "text": "Tontro Junction, Akyem Tafo, Eastern Region | 0598616671",
                    },
                    {
                        "title": "Amasaman branch",
                        "text": "Ga-West, Accra | 0248498755",
                    },
                    {
                        "title": "Front desk",
                        "text": "Listed as open 24/7. Contact the relevant branch to confirm current services.",
                    },
                ],
            },
        },
        {
            "key": "restaurant",
            "title": "Restaurant & dining",
            "content": {
                "title": "Dining & Rooftop Lounge",
                "intro": (
                    "Enjoy local cuisine at the on-site restaurant, then unwind at the "
                    "rooftop bar and lounge with city views. Browse the menu below, or "
                    "contact the hotel to confirm current selections and availability."
                ),
                "opening_hours": "For current restaurant and lounge hours, please contact the hotel.",
                "menu_url": MENU_URL,
                "menu_highlights": [],
                "media_ids": restaurant_media_ids if restaurant_media_ids is not None else [],
            },
        },
        {
            "key": "events",
            "title": "Events & conferences",
            "content": {
                "title": "Meetings, Conferences & Special Events",
                "intro": (
                    "Bring your guests together in a welcoming setting designed for "
                    "business gatherings and memorable occasions. The conference room "
                    "seats up to 100 guests, giving you room to host your next event."
                ),
                "capacity_text": (
                    "Our conference room accommodates up to 100 seated guests. It is "
                    "suited to conferences, business meetings, seminars, workshops and "
                    "private celebrations."
                ),
                "services": [
                    {
                        "title": "Conferences & business meetings",
                        "text": "Gather colleagues and guests in a dedicated conference-room setting.",
                    },
                    {
                        "title": "Seminars & workshops",
                        "text": "Bring a group together for presentations, training and discussion.",
                    },
                    {
                        "title": "Private celebrations",
                        "text": "A welcoming venue option for special occasions and group gatherings.",
                    },
                ],
                "enquiry_text": (
                    "Planning an event? Contact the Amasaman branch on 0248498755 "
                    "to discuss your date, guest count and preferred setup. Confirm "
                    "availability and event arrangements directly with the venue."
                ),
                "venue_url": EVENTS_URL,
                "media_ids": event_media_ids or [],
            },
        },
        {
            "key": "contact",
            "title": "Contact page",
            "content": {
                "intro": (
                    "Contact New Leaders Hotel and Events Centre for booking and service enquiries. "
                    "The hotel has branches in Akyem Tafo and Amasaman."
                ),
                "opening_hours": "Front desk: 24/7",
                "directions": (
                    "Akyem Tafo branch: Tontro Junction · 0598616671\n"
                    "Amasaman branch: Ga-West, Accra · 0248498755"
                ),
                "directions_url": MAPS_URL,
                "booking_url": BOOKING_URL,
                "map_embed_url": "",
            },
        },
        {
            "key": "footer",
            "title": "Footer",
            "content": {
                "about": "Hotel accommodation, dining and events in Akyem Tafo, Ghana.",
                "copyright": "New Leaders Hotel and Events Centre",
            },
        },
    ]


async def ensure_media(db, image: dict, order: int) -> str:
    source_url = image["source_url"]
    existing = await db.media.find_one({"source_url": source_url})
    if existing:
        return existing["_id"]

    filename = unquote(image["filename"])
    if filename == "logo.png":
        title, alt_text = "New Leaders Hotel logo", "New Leaders Hotel and Events Centre logo"
    elif filename == "official-video-poster":
        title, alt_text = "Official website video poster", "Image shown with the official hotel website video"
    elif image["category"] == "other":
        title, alt_text = "New Leaders Hotel favicon", "New Leaders Hotel and Events Centre icon"
    else:
        title = f"Official website gallery image {order + 1}"
        alt_text = "Hotel image from the official New Leaders Hotel website"

    mid = new_id()
    await db.media.insert_one({
        "_id": mid,
        "title": title,
        "description": "",
        "alt_text": alt_text,
        "category": image["category"],
        "status": "published",
        "order": order,
        "url": source_url,
        "variants": {"sm": source_url, "md": source_url, "lg": source_url},
        "width": None,
        "height": None,
        "size": 0,
        "storage_keys": [],
        "uploaded_by": "website-import",
        "source_url": source_url,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    })
    return mid


async def ensure_source_record(collection, query: dict, document: dict, label: str) -> None:
    existing = await collection.find_one(query)
    if existing and existing.get("source_url") != SITE_URL:
        print(f"  SKIP existing non-imported {label}")
        return
    if existing:
        document.setdefault("created_at", existing.get("created_at", utcnow()))
        await collection.update_one({"_id": existing["_id"]}, {"$set": document})
        print(f"  Updated imported {label}")
        return
    await collection.insert_one({"_id": new_id(), **document})
    print(f"  Added {label}")


async def import_content_items(db) -> None:
    items = [
        {
            "type": "facility",
            "title": "On-site restaurant",
            "body": "The official website describes an on-site restaurant serving local cuisine.",
            "question": "",
            "answer": "",
        },
        {
            "type": "facility",
            "title": "Rooftop bar and lounge",
            "body": "The official website describes a rooftop bar and lounge with city views.",
            "question": "",
            "answer": "",
        },
        {
            "type": "facility",
            "title": "Events centre",
            "body": "The official website identifies an events centre and links to The Word Events Centre in Amasaman.",
            "question": "",
            "answer": "",
        },
        {
            "type": "facility",
            "title": "24/7 front desk",
            "body": "The official website lists front desk hours as 24/7.",
            "question": "",
            "answer": "",
        },
        {
            "type": "facility",
            "title": "Conference room (up to 100 guests)",
            "body": "The events page confirms a conference room with seating for up to 100 guests. Confirm availability and preferred arrangements with the venue.",
            "question": "",
            "answer": "",
        },
        {
            "type": "faq",
            "title": "Hotel locations",
            "question": "Where are New Leaders Hotel and Events Centre's branches?",
            "answer": "The Akyem Tafo branch is at Tontro Junction in the Eastern Region. The Amasaman branch is in Ga-West, Accra.",
        },
        {
            "type": "faq",
            "title": "Branch contact numbers",
            "question": "How can I contact the branches?",
            "answer": "Call the Akyem Tafo branch on 0598616671 or the Amasaman branch on 0248498755.",
        },
        {
            "type": "faq",
            "title": "Front desk hours",
            "question": "What are the front desk hours?",
            "answer": "The official website lists the front desk as open 24/7.",
        },
        {
            "type": "faq",
            "title": "Conference room capacity",
            "question": "How many guests can the conference room accommodate?",
            "answer": "The conference room seats up to 100 guests. Contact the venue to confirm availability and event arrangements.",
        },
        {
            "type": "faq",
            "title": "Event options",
            "question": "What types of events can I enquire about?",
            "answer": "The venue lists conferences, business meetings, seminars, workshops and private celebrations. Contact the venue to discuss dates and arrangements.",
        },
        {
            "type": "faq",
            "title": "Room bookings",
            "question": "How can I enquire about a room booking?",
            "answer": "Use the Book Now form on the official website or contact the Akyem Tafo branch on 0598616671 or the Amasaman branch on 0248498755.",
        },
        {
            "type": "faq",
            "title": "Restaurant menu",
            "question": "Can I view the restaurant menu online?",
            "answer": "The restaurant menu is available from the official website. Contact the hotel to confirm current selections and availability.",
        },
        {
            "type": "event",
            "title": "Conferences & business meetings",
            "body": "Gather colleagues and guests in a dedicated conference-room setting. The room seats up to 100 guests; confirm availability and arrangements with the venue.",
        },
        {
            "type": "event",
            "title": "Seminars & workshops",
            "body": "Bring a group together for seminars, workshops, training and discussion. Contact the venue to confirm dates and arrangements.",
        },
        {
            "type": "event",
            "title": "Private celebrations",
            "body": "Enquire about the venue for private celebrations and special occasions. Contact the venue to discuss guest numbers, availability and arrangements.",
        },
    ]

    orders = {kind: 0 for kind in ("facility", "faq", "event")}
    image_titles = set(FACILITY_IMAGE_TITLES.values())
    image_records = await db.media.find(
        {"title": {"$in": list(image_titles)}, "status": "published"},
        {"_id": 1, "title": 1},
    ).to_list(None)
    image_ids_by_title = {record["title"]: record["_id"] for record in image_records}
    for missing_title in sorted(image_titles - set(image_ids_by_title)):
        print(f"  WARNING missing published facility image: {missing_title}")

    for item in items:
        kind = item["type"]
        identity = (
            {"type": kind, "question": item["question"]}
            if kind == "faq"
            else {"type": kind, "title": item["title"]}
        )
        current = await db.content_items.find_one(identity)
        image_title = FACILITY_IMAGE_TITLES.get(item["title"])
        image_id = image_ids_by_title.get(image_title) if image_title else None
        if current and current.get("source_url") == SITE_URL:
            image_id = current.get("media_id") or image_id
        document = {
            **item,
            "body": item.get("body", ""),
            "question": item.get("question", ""),
            "answer": item.get("answer", ""),
            "icon": "",
            "author": "",
            "extra": {},
            "media_id": image_id,
            "media_ids": [],
            "status": "published",
            "order": orders[kind],
            "verified": False,
            "source_url": SITE_URL,
            "updated_at": utcnow(),
        }
        orders[kind] += 1
        await ensure_source_record(
            db.content_items,
            identity,
            document,
            f"{kind} {item['title']}",
        )


async def import_site(db, manifest: dict) -> None:
    image_ids = {}
    for order, image in enumerate(manifest["images"]):
        image_id = await ensure_media(db, image, order)
        image_ids[unquote(image["filename"])] = image_id
    print(f"Registered {len(image_ids)} official-site image references.")

    hotel_settings = await db.hotel_settings.find_one({"_id": "main"})
    profile = make_profile(image_ids)
    current_profile = hotel_settings.get("profile") if hotel_settings else None
    if not current_profile or current_profile.get("source_url") == SITE_URL:
        await db.hotel_settings.update_one(
            {"_id": "main"},
            {"$set": {"profile": profile, "updated_at": utcnow()}},
            upsert=True,
        )
        print("Saved hotel profile.")
    else:
        print("Skipped existing hotel profile to preserve manual changes.")

    existing_events = await db.website_sections.find_one({"key": "events"})
    existing_events_content = (
        (existing_events or {}).get("published")
        or (existing_events or {}).get("draft")
        or {}
    )
    event_media_ids = existing_events_content.get("media_ids") or []
    existing_restaurant = await db.website_sections.find_one({"key": "restaurant"})
    existing_restaurant_content = (
        (existing_restaurant or {}).get("published")
        or (existing_restaurant or {}).get("draft")
        or {}
    )
    restaurant_media_ids = existing_restaurant_content.get("media_ids") or []
    for section in make_sections(image_ids, event_media_ids, restaurant_media_ids):
        await ensure_source_record(
            db.website_sections,
            {"key": section["key"]},
            {
                "key": section["key"],
                "title": section["title"],
                "draft": section["content"],
                "published": section["content"],
                "status": "published",
                "source_url": SITE_URL,
                "created_at": utcnow(),
                "updated_at": utcnow(),
                "published_at": utcnow(),
            },
            f"website section {section['key']}",
        )

    amenities = []
    for name in ("Cozy mattresses", "Modern conveniences", "City views"):
        key = name.lower()
        amenity = await db.amenities.find_one({"name_lower": key})
        if not amenity:
            aid = new_id()
            await db.amenities.insert_one({
                "_id": aid,
                "name": name,
                "name_lower": key,
                "icon": "",
                "source_url": SITE_URL,
                "created_at": utcnow(),
            })
            amenity = {"_id": aid}
        amenities.append(amenity["_id"])

    category = await db.room_categories.find_one({"slug": "luxurious-room"})
    if not category or category.get("source_url") == SITE_URL:
        category_doc = {
            "slug": "luxurious-room",
            "name": "Luxurious Room",
            "short_description": "Room type listed on the official website.",
            "full_description": (
                "The website describes the hotel's rooms as having comfortable mattresses, "
                "modern conveniences and city views. Room capacity, bed configuration and "
                "nightly rate are not published; confirm them before publishing this category."
            ),
            "default_rate_minor": 0,
            "max_occupancy": 2,
            "amenity_ids": amenities,
            "adult_capacity": None,
            "children_capacity": None,
            "included_guests": None,
            "extra_guest_fee_minor": 0,
            "bed_configuration": "",
            "room_size_sqm": None,
            "featured": False,
            "status": "draft",
            "main_media_id": None,
            "gallery_media_ids": [],
            "sort_order": 0,
            "is_sample": False,
            "source_url": SITE_URL,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        if category:
            await db.room_categories.update_one({"_id": category["_id"]}, {"$set": category_doc})
        else:
            await db.room_categories.insert_one({"_id": new_id(), "created_at": utcnow(), **category_doc})
        print("Added/updated Luxurious Room as a draft (rate and capacity require confirmation).")
    else:
        print("Skipped existing Luxurious Room category to preserve manual changes.")

    await import_content_items(db)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import verified hotel website content.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and summarize without writing to MongoDB.")
    args = parser.parse_args()
    manifest = load_manifest()
    if args.dry_run:
        print(f"Source: {SITE_URL}")
        print(f"Image references: {len(manifest['images'])}")
        print("Website sections: 7")
        print("Room category: 1 draft; no rate or capacity is assumed as confirmed.")
        return

    if not get_config().mongodb_url:
        raise RuntimeError("MONGODB_URL is empty; set your MongoDB Atlas URI before importing.")
    await database.connect()
    try:
        await import_site(database.get_db(), manifest)
    finally:
        await database.close()
    print("Website content import complete.")


if __name__ == "__main__":
    asyncio.run(main())
