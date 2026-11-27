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
