async def test_public_gallery_includes_all_published_media_categories(client, db):
    images = [
        {"_id": "gallery-image", "category": "gallery", "status": "published"},
        {"_id": "room-image", "category": "room", "status": "published"},
        {"_id": "draft-image", "category": "event", "status": "draft"},
    ]
    for image in images:
        await db.media.insert_one({
            **image,
            "url": f"https://images.example/{image['_id']}.jpg",
            "variants": {},
            "alt_text": image["_id"],
            "title": image["_id"],
        })

    response = await client.get("/api/v1/website/gallery")

    assert response.status_code == 200
    results = response.json()
    assert {image["id"] for image in results} == {"gallery-image", "room-image"}
