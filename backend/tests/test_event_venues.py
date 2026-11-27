import asyncio
from datetime import timedelta

from app import utils
from .conftest import future, guest


async def setup_venue(client, admin_h, *, capacity=100, rate=10000):
    await client.post("/api/v1/event-venues/admin/defaults", headers=admin_h)
    venues = (await client.get("/api/v1/event-venues/admin", headers=admin_h)).json()
    venue = next(v for v in venues if v["slug"] == "conference-room-100")
    if capacity != venue["capacity"] or rate:
        updated = await client.patch(
            f"/api/v1/event-venues/admin/{venue['id']}", headers=admin_h,
            json={"capacity": capacity, "hourly_rate_minor": rate, "status": "published"},
        )
        assert updated.status_code == 200, updated.text
        venue = updated.json()
    return venue


def event_body(venue_id, *, start="09:00", end="10:00", attendees=40, email="event@example.com"):
    return {
        "venue_id": venue_id, "date": future(10), "start_time": start, "end_time": end,
        "attendees": attendees, "event_type": "Engagement", "guest": guest(email),
    }


async def test_event_venue_defaults_publish_and_hourly_quote(client, admin_h):
    await client.post("/api/v1/event-venues/admin/defaults", headers=admin_h)
    venues = (await client.get("/api/v1/event-venues/admin", headers=admin_h)).json()
    by_slug = {v["slug"]: v for v in venues}
    assert by_slug["conference-room-100"]["capacity"] == 100
    assert by_slug["conference-room-30"]["capacity"] == 30
    assert by_slug["event-centre"]["capacity"] >= 501
    assert by_slug["event-centre"]["capacity_confirmed"] is False
    assert all(v["status"] == "draft" for v in venues)

    refused = await client.patch(
        f"/api/v1/event-venues/admin/{by_slug['event-centre']['id']}",
        headers=admin_h,
        json={"hourly_rate_minor": 10000, "status": "published"},
    )
    assert refused.status_code == 422
    confirmed = await client.patch(
        f"/api/v1/event-venues/admin/{by_slug['event-centre']['id']}",
        headers=admin_h,
        json={"hourly_rate_minor": 10000, "capacity_confirmed": True, "status": "published"},
    )
    assert confirmed.status_code == 200

    venue = await setup_venue(client, admin_h, capacity=100)
    public = await client.get("/api/v1/event-venues")
    assert public.status_code == 200 and venue["id"] in [v["id"] for v in public.json()]
    request = {k: v for k, v in event_body(venue["id"], start="09:00", end="10:30").items() if k != "guest"}
    quote = await client.post("/api/v1/event-bookings/quote", json=request)
    assert quote.status_code == 200, quote.text
    assert quote.json()["duration_minutes"] == 90
    assert quote.json()["subtotal_minor"] == 15000
    assert quote.json()["available"] is True
    too_many = await client.post("/api/v1/event-bookings/quote", json={**request, "attendees": 101})
    assert too_many.status_code == 400


async def test_event_booking_prevents_overlapping_slots_and_cancel_releases_them(client, admin_h, db):
    venue = await setup_venue(client, admin_h)
    first = await client.post("/api/v1/event-bookings", json=event_body(venue["id"]))
    assert first.status_code == 201, first.text
    reservation = await db.reservations.find_one({"reference": first.json()["reference"]})
    conflict = await client.post(
        "/api/v1/event-bookings",
        json=event_body(venue["id"], start="09:45", end="10:45", email="overlap@example.com"),
    )
    assert conflict.status_code == 409

    cancelled = await client.post(
        f"/api/v1/event-bookings/admin/{reservation['_id']}/cancel",
        headers=admin_h, json={"reason": "Guest changed plans"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    released = await client.post(
        "/api/v1/event-bookings",
        json=event_body(venue["id"], email="replacement@example.com"),
    )
    assert released.status_code == 201, released.text


async def test_concurrent_event_bookings_cannot_claim_same_time(client, admin_h):
    venue = await setup_venue(client, admin_h)
    results = await asyncio.gather(*[
        client.post(
            "/api/v1/event-bookings",
            json=event_body(venue["id"], email=f"event{i}@example.com"),
        )
        for i in range(6)
    ])
    codes = [response.status_code for response in results]
    assert codes.count(201) == 1 and codes.count(409) == 5


async def test_event_slot_holds_expire_and_paid_booking_confirms(client, admin_h, db, gateway):
    venue = await setup_venue(client, admin_h)
    response = await client.post("/api/v1/event-bookings", json=event_body(venue["id"]))
    assert response.status_code == 201, response.text
    reference = response.json()["reference"]
    payment_reference = response.json()["payment_reference"]
    reservation = await db.reservations.find_one({"reference": reference})
    assert reservation["booking_type"] == "event"
    room_reservations = await client.get("/api/v1/reservations", headers=admin_h)
    assert all(item.get("booking_type") != "event" for item in room_reservations.json()["items"])
    assert (await client.get(f"/api/v1/reservations/{reservation['_id']}", headers=admin_h)).status_code == 404
    assert await db.event_booking_slots.count_documents({"reservation_id": reservation["_id"]}) == 4
    gateway.pay(payment_reference)
    status = await client.get(f"/api/v1/bookings/payment-status/{payment_reference}")
    assert status.status_code == 200, status.text
    assert status.json()["booking_type"] == "event"
    assert status.json()["reservation_status"] == "confirmed"
    held = await db.event_booking_slots.find({"reservation_id": reservation["_id"]}).to_list(None)
    assert len(held) == 4 and all(slot["hold_expires_at"] is None for slot in held)

    # A confirmed booking keeps the time unavailable until staff cancels it.
    conflict = await client.post("/api/v1/event-bookings", json=event_body(venue["id"], email="other@example.com"))
    assert conflict.status_code == 409


async def test_expired_event_holds_release_the_time(client, admin_h, db):
    venue = await setup_venue(client, admin_h)
    response = await client.post("/api/v1/event-bookings", json=event_body(venue["id"]))
    assert response.status_code == 201, response.text
    reservation = await db.reservations.find_one({"reference": response.json()["reference"]})
    expired_at = utils.utcnow() - timedelta(minutes=1)
    await db.reservations.update_one({"_id": reservation["_id"]}, {"$set": {"hold_expires_at": expired_at}})
    await db.event_booking_slots.update_many({"reservation_id": reservation["_id"]}, {"$set": {"hold_expires_at": expired_at}})

    from app.services.reservations import expire_holds

    assert await expire_holds(db) == 1
    replacement = await client.post(
        "/api/v1/event-bookings",
        json=event_body(venue["id"], email="replacement@example.com"),
    )
    assert replacement.status_code == 201, replacement.text
