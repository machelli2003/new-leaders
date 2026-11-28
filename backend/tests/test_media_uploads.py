import io

from PIL import Image

from app.config import get_config


async def test_oversized_upload_is_rejected_before_image_processing(client, admin_h, monkeypatch):
    settings = get_config()
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    response = await client.post(
        "/api/v1/media",
        headers=admin_h,
        files=[("files", ("large.jpg", b"x" * (1024 * 1024 + 1), "image/jpeg"))],
    )
    assert response.status_code == 413
    assert response.json()["error"]["message"] == "Image exceeds 1 MB"


async def test_non_image_upload_is_rejected_even_with_image_content_type(client, admin_h):
    response = await client.post(
        "/api/v1/media",
        headers=admin_h,
        files=[("files", ("fake.jpg", b"not an image", "image/jpeg"))],
    )
    assert response.status_code == 415


async def test_image_upload_is_reencoded_regardless_of_filename_and_content_type(client, admin_h):
    image = Image.new("RGB", (4, 4), "red")
    raw = io.BytesIO()
    image.save(raw, format="PNG")

    response = await client.post(
        "/api/v1/media",
        headers=admin_h,
        files=[("files", ("payload.exe", raw.getvalue(), "application/octet-stream"))],
    )
    assert response.status_code == 201
    item = response.json()[0]
    assert item["url"].endswith(".webp")
    assert all(url.endswith(".webp") for url in item["variants"].values())
