"""
Seed real hotel data for New Leaders Hotel and Events Centre.
Registers downloaded images into the media library, sets the hotel profile,
and seeds website content from the scraped website.

Usage (from backend/): python -m scripts.seed_real_data
"""
import asyncio
import os
import sys

# Allow running from backend/ dir
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import db as database
from app.config import get_config
from app.hotel_settings import save_section
from app.services import storage
from app.utils import new_id, utcnow


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

# Map filename -> (category, title, alt_text)
IMAGES = [
    ("logo.png",          "logo",    "New Leaders Hotel Logo",                       "New Leaders Hotel and Events Centre logo"),
    ("aerial_view.jpg",   "banner",  "Aerial View – New Leaders Hotel",              "Aerial drone view of New Leaders Hotel and Events Centre, Akyem Tafo"),
    ("hotel_photo_1.jpg", "gallery", "New Leaders Hotel – Exterior",                 "Exterior view of New Leaders Hotel and Events Centre"),
    ("hotel_photo_2.jpg", "gallery", "New Leaders Hotel – Lobby Area",               "Hotel lobby area at New Leaders Hotel"),
    ("hotel_photo_3.jpg", "gallery", "New Leaders Hotel – Guest Area",               "Guest area at New Leaders Hotel"),
    ("hotel_photo_4.jpg", "gallery", "New Leaders Hotel – Facilities",               "Hotel facilities at New Leaders Hotel"),
    ("hotel_photo_5.jpg", "gallery", "New Leaders Hotel – Common Area",              "Common area at New Leaders Hotel and Events Centre"),
    ("hotel_photo_6.jpg", "gallery", "New Leaders Hotel – Events Centre",            "Events centre at New Leaders Hotel"),
    ("room_photo_1.jpg",  "room",    "New Leaders Hotel – Luxurious Room",           "Luxurious room at New Leaders Hotel and Events Centre"),
    ("room_photo_2.jpg",  "room",    "New Leaders Hotel – Reception",                "Reception area at New Leaders Hotel"),
    ("favicon.jpg",       "other",   "New Leaders Hotel – Property View",            "Property view of New Leaders Hotel"),
]


async def register_image(db, cfg, filename, category, title, alt_text):
    path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        print(f"  SKIP (not found): {filename}")
        return None

    # Check if already registered
    existing = await db.media.find_one({"title": title})
    if existing:
        print(f"  EXISTS: {title} -> {existing['_id']}")
        return existing["_id"]

    with open(path, "rb") as f:
        raw = f.read()

    try:
        info = storage.store_image(raw)
    except Exception as e:
        print(f"  FAIL processing {filename}: {e}")
        return None

    mid = new_id()
    doc = {
        "_id": mid,
        "title": title,
        "description": "",
        "alt_text": alt_text,
        "category": category,
        "status": "published",
        "order": 0,
        "url": info["url"],
        "variants": info["variants"],
        "width": info["width"],
        "height": info["height"],
        "size": info["size"],
        "storage_keys": info["keys"],
        "uploaded_by": "system",
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    await db.media.insert_one(doc)
    print(f"  OK: {title} -> {mid}")
    return mid


async def main():
    await database.connect()
    db = database.get_db()
    cfg = get_config()

    print("=== Registering images in media library ===")
    media_ids = {}
    for filename, category, title, alt_text in IMAGES:
        mid = await register_image(db, cfg, filename, category, title, alt_text)
        media_ids[filename] = mid

    logo_id = media_ids.get("logo.png")
    banner_ids = [
        media_ids.get("aerial_view.jpg"),
        media_ids.get("hotel_photo_1.jpg"),
        media_ids.get("hotel_photo_2.jpg"),
    ]
    banner_ids = [b for b in banner_ids if b]

    print(f"\n=== Saving hotel profile ===")
    profile = {
        "name": "New Leaders Hotel and Events Centre",
        "branch_name": "Akyem Tafo Branch (Eastern Region)",
        "description": (
            "Experience luxury and excellent service at New Leaders Hotel and Events Centre, "
            "located at Tontro Junction, Akyem Tafo in the Eastern Region of Ghana. "
            "We offer a range of comfortable accommodations, diverse dining options, "
            "and a perfect events venue for unforgettable moments. "
            "Whether you're travelling solo or as a group, our hotel provides cozy rooms "
            "with modern conveniences and breathtaking city views."
        ),
        "address": "Tontro Junction, Akyem Tafo",
        "town": "Akyem Tafo",
        "region": "Eastern Region",
        "country": "Ghana",
        "latitude": 6.245934,
        "longitude": -0.381074,
        "phones": ["0598616671", "0248498755"],
        "emails": [],
        "website_domain": "newleadershotelandeventcentre.com",
        "socials": {
            "facebook": "",
            "instagram": "",
            "x": "",
            "tiktok": "",
            "youtube": "",
            "whatsapp": "0598616671",
        },
        "logo_media_id": logo_id,
        "banner_media_ids": banner_ids,
    }
    await save_section(db, "profile", profile)
    print(f"  Profile saved. Logo ID: {logo_id}, Banners: {len(banner_ids)}")

    print(f"\n=== Saving booking settings ===")
    booking = {
        "currency": "GHS",
        "check_in_time": "14:00",
        "check_out_time": "12:00",
        "min_nights": 1,
        "max_nights": 30,
        "max_rooms_per_booking": 5,
        "max_advance_days": 365,
        "hold_minutes": 30,
        "weekend_days": [4, 5],
        "checkin_requires": "none",
        "booking_rules": (
            "Check-in time is 2:00 PM and check-out time is 12:00 PM (noon). "
            "Early check-in and late check-out are subject to availability. "
            "A valid government-issued ID is required at check-in. "
            "The Front Desk is open 24/7."
        ),
        "setup_confirmed": True,
    }
    await save_section(db, "booking", booking)
    print("  Booking settings saved.")

    # Seed amenities
    print(f"\n=== Seeding amenities ===")
    amenities_list = [
        "Free Wi-Fi", "Air Conditioning", "Television", "Private Bathroom",
        "Hot Water", "24/7 Front Desk", "Restaurant", "Events Centre",
        "Parking", "Rooftop Bar & Lounge", "Room Service",
    ]
    amenity_ids = []
    for name in amenities_list:
        existing = await db.amenities.find_one({"name_lower": name.lower()})
        if existing:
            amenity_ids.append(existing["_id"])
            print(f"  EXISTS: {name}")
        else:
            aid = new_id()
            await db.amenities.insert_one({
                "_id": aid, "name": name, "name_lower": name.lower(),
                "icon": "", "created_at": utcnow()
            })
            amenity_ids.append(aid)
            print(f"  Added: {name}")

    # Seed room categories
    print(f"\n=== Seeding room categories ===")
    room_img_id = media_ids.get("room_photo_1.jpg")
    reception_img_id = media_ids.get("room_photo_2.jpg")
    hotel_img_ids = [v for k, v in media_ids.items() if v and k.startswith("hotel_photo")]

    categories = [
        {
            "name": "Standard Room",
            "short_description": "Comfortable room with modern amenities and city views.",
            "full_description": (
                "Our Standard Rooms are designed to offer maximum comfort during your stay. "
                "Each room features a cozy mattress, air conditioning, television, private bathroom with hot water, "
                "and free Wi-Fi. Perfect for solo travellers or couples."
            ),
            "default_rate_minor": 30000,  # GHS 300 / night — placeholder, update with real rate
            "max_occupancy": 2,
            "included_guests": 2,
            "extra_guest_fee_minor": 0,
            "bed_configuration": "1 Double Bed",
            "room_size_sqm": None,
            "featured": False,
            "status": "published",
            "main_media_id": room_img_id,
            "gallery_media_ids": [room_img_id] if room_img_id else [],
        },
        {
            "name": "Luxurious Room",
            "short_description": "Spacious luxurious room with premium furnishings and breathtaking views.",
            "full_description": (
                "Experience the pinnacle of comfort in our Luxurious Rooms at New Leaders Hotel. "
                "Featuring premium furnishings, air conditioning, flat-screen television, "
                "private bathroom with hot water, free Wi-Fi, and stunning city views. "
                "Ideal for business travellers and those seeking an elevated stay."
            ),
            "default_rate_minor": 50000,  # GHS 500 / night — placeholder, update with real rate
            "max_occupancy": 2,
            "included_guests": 2,
            "extra_guest_fee_minor": 0,
            "bed_configuration": "1 King Bed",
            "room_size_sqm": None,
            "featured": True,
            "status": "published",
            "main_media_id": room_img_id,
            "gallery_media_ids": [room_img_id, reception_img_id] if reception_img_id else ([room_img_id] if room_img_id else []),
        },
        {
            "name": "Family Room",
            "short_description": "Spacious family room accommodating up to 4 guests comfortably.",
            "full_description": (
                "Our Family Rooms are ideal for group travel, offering ample space for up to 4 guests. "
                "Featuring two double beds, air conditioning, television, private bathroom with hot water, "
                "and free Wi-Fi. The perfect choice for families visiting Akyem Tafo and the Eastern Region."
            ),
            "default_rate_minor": 70000,  # GHS 700 / night — placeholder, update with real rate
            "max_occupancy": 4,
            "included_guests": 4,
            "extra_guest_fee_minor": 0,
            "bed_configuration": "2 Double Beds",
            "room_size_sqm": None,
            "featured": True,
            "status": "published",
            "main_media_id": room_img_id,
            "gallery_media_ids": [room_img_id] if room_img_id else [],
        },
    ]

    cat_ids = []
    for i, cat in enumerate(categories):
        from app.utils import slugify
        slug = slugify(cat["name"])
        existing = await db.room_categories.find_one({"slug": slug})
        if existing:
            cat_ids.append(existing["_id"])
            print(f"  EXISTS: {cat['name']}")
            continue
        cid = new_id()
        await db.room_categories.insert_one({
            "_id": cid,
            "slug": slug,
            "amenity_ids": amenity_ids,
            "adult_capacity": None,
            "children_capacity": None,
            "sort_order": i,
            "is_sample": False,
            "created_at": utcnow(),
            "updated_at": utcnow(),
            **cat,
        })
        cat_ids.append(cid)
        print(f"  Added: {cat['name']} (GHS {cat['default_rate_minor']//100}/night)")

    print(f"\n=== Seeding website sections ===")

    gallery_all = [v for k, v in media_ids.items() if v and k not in ("logo.png", "favicon.jpg")]

    sections = [
        {
            "key": "hero",
            "title": "Welcome to New Leaders Hotel and Events Centre",
            "body": (
                "Where Excellent Service is Provided.\n\n"
                "Experience luxury at our hotel and events centre with top-notch accommodations, "
                "diverse dining options, and a perfect event venue for unforgettable moments. "
                "Located at Tontro Junction, Akyem Tafo — Eastern Region, Ghana."
            ),
            "cta_label": "Book Now",
            "cta_url": "/booking/search",
            "media_ids": banner_ids,
            "status": "published",
            "sort_order": 0,
        },
        {
            "key": "about",
            "title": "About New Leaders Hotel and Events Centre",
            "body": (
                "New Leaders Hotel and Events Centre is a premier hospitality destination in Akyem Tafo, "
                "Eastern Region of Ghana. We pride ourselves on delivering excellent service to every guest.\n\n"
                "Our accommodations are designed to meet the demands of all visitors — whether you're travelling "
                "solo, as a couple, or as a group. We have the ideal room for you, with cozy mattresses, "
                "contemporary conveniences, and breathtaking city views.\n\n"
                "We also operate a second branch in Amasaman, Ga-West, Accra, extending our excellent service "
                "across Ghana."
            ),
            "cta_label": "View Our Rooms",
            "cta_url": "/rooms",
            "media_ids": [media_ids.get("hotel_photo_1.jpg")] if media_ids.get("hotel_photo_1.jpg") else [],
            "status": "published",
            "sort_order": 1,
        },
        {
            "key": "dining",
            "title": "Our Dining Experience",
            "body": (
                "At New Leaders Hotel and Events Centre, we take pride in offering a diverse range of dining options. "
                "From our on-site restaurant serving authentic local Ghanaian cuisine to our rooftop bar and lounge "
                "with breathtaking views of the city, we have something for every palate.\n\n"
                "Our expert chefs use only the freshest ingredients to create delicious meals that will leave you "
                "craving more. Whether you're joining us for breakfast, lunch, or dinner, we promise a memorable "
                "dining experience."
            ),
            "cta_label": "",
            "cta_url": "",
            "media_ids": [media_ids.get("hotel_photo_5.jpg")] if media_ids.get("hotel_photo_5.jpg") else [],
            "status": "published",
            "sort_order": 2,
        },
        {
            "key": "events",
            "title": "Events & Conferences",
            "body": (
                "New Leaders Hotel and Events Centre is the perfect venue for your next event. "
                "Whether it's a corporate conference, wedding reception, birthday celebration, or any other "
                "special occasion, our events centre is fully equipped to make your event a success.\n\n"
                "Our professional events team is dedicated to ensuring every detail is taken care of, "
                "so you can focus on enjoying your special day."
            ),
            "cta_label": "Contact Us",
            "cta_url": "/contact",
            "media_ids": [media_ids.get("hotel_photo_6.jpg")] if media_ids.get("hotel_photo_6.jpg") else [],
            "status": "published",
            "sort_order": 3,
        },
        {
            "key": "location",
            "title": "Our Location",
            "body": (
                "Located at Tontro Junction, Akyem Tafo in the Eastern Region of Ghana, "
                "New Leaders Hotel and Events Centre is the perfect base for exploring the sights and sounds of the city. "
                "We are within a 5-minute drive from Akyem Tafo township.\n\n"
                "Our prime location offers convenient access to public transportation, making it easy to explore the city.\n\n"
                "**Akyem Tafo Branch (Eastern Region):** 0598616671\n"
                "**Amasaman Branch (Ga-West, Accra):** 0248498755\n\n"
                "Front Desk Hours: 24/7"
            ),
            "cta_label": "Get Directions",
            "cta_url": "https://maps.google.com/?q=6.245934,-0.381074",
            "media_ids": [media_ids.get("aerial_view.jpg")] if media_ids.get("aerial_view.jpg") else [],
            "status": "published",
            "sort_order": 4,
        },
        {
            "key": "gallery",
            "title": "Gallery",
            "body": "Immerse yourself in New Leaders Hotel and Events Centre: a gallery of images.",
            "cta_label": "",
            "cta_url": "",
            "media_ids": gallery_all,
            "status": "published",
            "sort_order": 5,
        },
    ]

    for sec in sections:
        existing = await db.website_sections.find_one({"key": sec["key"]})
        if existing:
            await db.website_sections.update_one(
                {"_id": existing["_id"]},
                {"$set": {**sec, "updated_at": utcnow()}}
            )
            print(f"  UPDATED section: {sec['key']}")
        else:
            await db.website_sections.insert_one({
                "_id": new_id(),
                "created_at": utcnow(),
                "updated_at": utcnow(),
                **sec,
            })
            print(f"  Added section: {sec['key']}")

    print(f"\n=== Seeding facilities ===")
    facilities = [
        ("24/7 Front Desk", "Our front desk is staffed around the clock to assist you with any needs.", media_ids.get("hotel_photo_2.jpg")),
        ("Restaurant & Dining", "On-site restaurant serving local Ghanaian cuisine and international dishes.", media_ids.get("hotel_photo_5.jpg")),
        ("Rooftop Bar & Lounge", "Enjoy breathtaking city views from our rooftop bar and lounge.", media_ids.get("hotel_photo_3.jpg")),
        ("Events Centre", "Fully equipped events centre for conferences, weddings, and special occasions.", media_ids.get("hotel_photo_6.jpg")),
        ("Free Parking", "Complimentary parking available for all hotel guests.", None),
        ("Free Wi-Fi", "High-speed wireless internet throughout the hotel.", None),
        ("Room Service", "In-room dining available for hotel guests.", None),
    ]
    for name, desc, img_id in facilities:
        existing = await db.content_items.find_one({"type": "facility", "title": name})
        if existing:
            print(f"  EXISTS facility: {name}")
            continue
        doc = {
            "_id": new_id(),
            "type": "facility",
            "title": name,
            "description": desc,
            "body": "",
            "question": None,
            "answer": None,
            "status": "published",
            "media_ids": [img_id] if img_id else [],
            "sort_order": 0,
            "is_sample": False,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        await db.content_items.insert_one(doc)
        print(f"  Added facility: {name}")

    print("\n✅ All done! Hotel data seeded successfully.")
    print(f"   Logo ID: {logo_id}")
    print(f"   Banner IDs: {banner_ids}")
    print(f"   Room categories: {len(cat_ids)}")
    print(f"   Media items: {len([v for v in media_ids.values() if v])}")
    print("\n⚠️  NOTE: Room rates are placeholder values. Please update them in Admin → Rooms.")
    print("⚠️  NOTE: Please add real email addresses in Admin → Settings → Profile.")

    await database.close()


if __name__ == "__main__":
    asyncio.run(main())
