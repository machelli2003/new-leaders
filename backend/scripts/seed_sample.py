"""DEVELOPMENT ONLY: loads clearly-marked SAMPLE data (categories, rooms, prices, amenities).
Every record has is_sample=true and a "(SAMPLE)" suffix. None of it is confirmed hotel information.
Replace/delete it through the dashboard once real data is available.

Usage (from backend/):  python -m scripts.seed_sample"""
import asyncio

from app import db as database
from app.utils import new_id, slugify, utcnow

AMENITIES = ["Free Wi-Fi", "Air conditioning", "Television", "Private bathroom", "Hot water"]
CATS = [("Standard", 25000, 2, "1 double bed"), ("Executive", 40000, 3, "1 king bed"), ("Family", 65000, 4, "2 double beds")]


async def main():
    await database.connect()
    db = database.get_db()
    ids = []
    for a in AMENITIES:
        if not await db.amenities.find_one({"name_lower": a.lower()}):
            d = {"_id": new_id(), "name": a, "name_lower": a.lower(), "icon": "", "created_at": utcnow()}
            await db.amenities.insert_one(d)
        ids.append((await db.amenities.find_one({"name_lower": a.lower()}))["_id"])
    for i, (name, rate, occ, beds) in enumerate(CATS):
        full = f"{name} (SAMPLE)"
        if await db.room_categories.find_one({"name": full}):
            continue
        cid = new_id()
        await db.room_categories.insert_one({"_id": cid, "name": full, "slug": slugify(full), "short_description": "SAMPLE DATA – replace with real description.",
            "full_description": "", "default_rate_minor": rate, "max_occupancy": occ, "adult_capacity": None, "children_capacity": None, "included_guests": None,
            "extra_guest_fee_minor": 0, "bed_configuration": beds, "room_size_sqm": None, "amenity_ids": ids, "featured": i < 2, "status": "published",
            "main_media_id": None, "gallery_media_ids": [], "sort_order": i, "is_sample": True, "created_at": utcnow(), "updated_at": utcnow()})
        for n in range(1, 4):
            num = f"S{i + 1}0{n}"
            await db.rooms.insert_one({"_id": new_id(), "number": num, "category_id": cid, "floor": str(i + 1), "description": "", "bed_configuration": "",
                "max_occupancy_override": None, "price_override_minor": None, "operational_status": "active", "photo_media_ids": [], "internal_notes": "SAMPLE room",
                "is_sample": True, "archived": False, "occupancy_status": "vacant", "housekeeping_status": "ready", "created_at": utcnow(), "updated_at": utcnow()})
    print("Sample data loaded (all marked SAMPLE).")
    await database.close()


if __name__ == "__main__":
    asyncio.run(main())
