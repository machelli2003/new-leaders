import asyncio
from datetime import timedelta

from app import utils
from .conftest import future, guest, login, make_user, stay


async def book(client, hotel, **kw):
    r = await client.post("/api/v1/bookings", json={**stay(hotel, **{k: v for k, v in kw.items() if k in ("qty", "cat", "d_in", "d_out")}),
                                                    "guest": kw.get("guest", guest())})
    return r


async def test_search_and_quote_are_server_calculated(client, hotel):
    r = await client.post("/api/v1/availability/search", json=stay(hotel))
    assert r.status_code == 200
    by = {c["name"]: c for c in r.json()}
    assert by["Standard"]["available_rooms"] == 3 and by["Executive"]["available_rooms"] == 1
    assert by["Standard"]["per_room_total_minor"] == 100000  # 2 nights x 500.00 in pesewas
    q = (await client.post("/api/v1/bookings/quote", json=stay(hotel, qty=2))).json()
    assert q["total_minor"] == 200000 and q["nights"] == 2


async def test_checkout_day_is_not_an_occupied_night(client, hotel):
    a = await book(client, hotel, cat="exe", d_in=10, d_out=12)
    assert a.status_code == 201
    # same-day turnover: next guest arrives on the first guest's check-out date
    b = await book(client, hotel, cat="exe", d_in=12, d_out=14, guest=guest("kofi@example.com"))
    assert b.status_code == 201, b.text
    # overlapping stay is refused (only one Executive room)
    c = await book(client, hotel, cat="exe", d_in=11, d_out=13, guest=guest("c@example.com"))
    assert c.status_code == 409


async def test_concurrent_bookings_never_double_book(client, hotel):
    results = await asyncio.gather(*[
        client.post("/api/v1/bookings", json={**stay(hotel, cat="exe"), "guest": guest(f"g{i}@example.com")}) for i in range(8)])
    codes = sorted(r.status_code for r in results)
    assert codes.count(201) == 1 and codes.count(409) == 7


async def test_multi_room_allocates_distinct_rooms(client, hotel, admin_h):
    r = await client.post("/api/v1/bookings", json={**stay(hotel, qty=3), "adults": 3, "guest": guest()})
    assert r.status_code == 201, r.text
    d = (await client.get(f"/api/v1/reservations/{(await client.get('/api/v1/reservations', headers=admin_h)).json()['items'][0]['id']}", headers=admin_h)).json()
    nums = [x["room_number"] for x in d["rooms"]]
    assert len(set(nums)) == 3
    assert (await book(client, hotel, qty=1, guest=guest("z@example.com"))).status_code == 409  # all 3 held


async def test_hold_expiry_releases_inventory(client, hotel, db):
    from app.services.reservations import expire_holds

    r = await book(client, hotel, cat="exe")
    assert r.status_code == 201
    await db.reservations.update_many({}, {"$set": {"hold_expires_at": utils.utcnow() - timedelta(minutes=1)}})
    await db.room_nights.update_many({}, {"$set": {"hold_expires_at": utils.utcnow() - timedelta(minutes=1)}})
    # even before the sweeper runs, an expired hold does not block a new customer
    assert (await book(client, hotel, cat="exe", guest=guest("n@example.com"))).status_code == 201
    await db.reservations.update_one({"status": "pending", "guest.email": "ama@example.com"}, {"$set": {"hold_expires_at": utils.utcnow() - timedelta(minutes=1)}})
    n = await expire_holds(db)
    assert n >= 1
    assert (await db.reservations.find_one({"guest.email": "ama@example.com"}))["status"] == "expired"


async def test_validation_rules(client, hotel):
    bad = {**stay(hotel), "check_out": future(10)}
    assert (await client.post("/api/v1/availability/search", json=bad)).status_code == 400
    past = {**stay(hotel), "check_in": future(-3), "check_out": future(-1)}
    assert (await client.post("/api/v1/bookings", json={**past, "guest": guest()})).status_code == 400
    too_many = {**stay(hotel, cat="exe"), "adults": 4}
    assert (await client.post("/api/v1/bookings", json={**too_many, "guest": guest()})).status_code == 400
    unpublished = await client.post("/api/v1/bookings/quote", json={**stay(hotel), "selections": [{"category_id": "nope", "quantity": 1}]})
    assert unpublished.status_code == 404


async def test_staff_walk_in_manual_assignment_and_reassign(client, hotel, recep_h, manager_h):
    body = {**stay(hotel, d_in=0, d_out=2), "guest": {"name": "Walk In", "phone": "0201112222"}, "source": "walk_in"}
    r = await client.post("/api/v1/reservations", headers=recep_h, json=body)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["reservation"]["status"] == "confirmed" and d["reservation"]["source"] == "walk_in"
    rr = d["rooms"][0]
    free = (await client.get(f"/api/v1/availability/rooms?check_in={future(0)}&check_out={future(2)}&category_id={hotel['std']['id']}", headers=recep_h)).json()
    assert rr["room_number"] not in [f["number"] for f in free] and len(free) == 2
    # reassign to another room (receptionist has reservations.assign)
    target = free[0]
    ok = await client.post(f"/api/v1/reservations/{d['reservation']['id']}/rooms/{rr['id']}/assign", headers=recep_h, json={"room_id": target["id"], "reason": "guest request"})
    assert ok.status_code == 200
    # old room is free again, target is taken
    free2 = (await client.get(f"/api/v1/availability/rooms?check_in={future(0)}&check_out={future(2)}&category_id={hotel['std']['id']}", headers=recep_h)).json()
    assert rr["room_number"] in [f["number"] for f in free2] and target["number"] not in [f["number"] for f in free2]
    # cannot reassign into an occupied room
    other = await client.post("/api/v1/reservations", headers=recep_h, json={**body, "guest": {"name": "Second", "phone": "0201113333"}})
    other_room = other.json()["rooms"][0]["room_id"]
    bad = await client.post(f"/api/v1/reservations/{d['reservation']['id']}/rooms/{rr['id']}/assign", headers=recep_h, json={"room_id": other_room})
    assert bad.status_code == 409
    hist = (await client.get(f"/api/v1/reservations/{d['reservation']['id']}", headers=manager_h)).json()["rooms"][0]["assignment_history"]
    assert len(hist) == 2


async def test_modify_dates_requotes_and_preserves_history(client, hotel, admin_h, manager_h):
    r = (await client.post("/api/v1/reservations", headers=manager_h, json={**stay(hotel), "guest": {"name": "Guest One", "phone": "0200000001"}})).json()
    rid = r["reservation"]["id"]
    assert r["reservation"]["total_amount"] == 100000
    # price change after booking must not change existing booking ... until the booking itself is modified
    await client.patch(f"/api/v1/room-categories/{hotel['std']['id']}", headers=admin_h, json={"default_rate_minor": 70000})
    again = (await client.get(f"/api/v1/reservations/{rid}", headers=manager_h)).json()
    assert again["reservation"]["total_amount"] == 100000
    m = await client.post(f"/api/v1/reservations/{rid}/modify-dates", headers=manager_h, json={"check_in": future(10), "check_out": future(13), "reason": "extended"})
    assert m.status_code == 200
    assert m.json()["total_amount"] == 3 * 70000
    assert len(m.json()["pricing_history"]) == 1 and m.json()["pricing_history"][0]["pricing"]["total_minor"] == 100000


async def test_modify_dates_conflict_rolls_back(client, hotel, manager_h):
    a = (await client.post("/api/v1/reservations", headers=manager_h, json={**stay(hotel, cat="exe", d_in=10, d_out=12), "guest": {"name": "Guest A", "phone": "0200000002"}})).json()
    await client.post("/api/v1/reservations", headers=manager_h, json={**stay(hotel, cat="exe", d_in=13, d_out=15), "guest": {"name": "Guest B", "phone": "0200000003"}})
    bad = await client.post(f"/api/v1/reservations/{a['reservation']['id']}/modify-dates", headers=manager_h, json={"check_in": future(10), "check_out": future(14)})
    assert bad.status_code == 409
    ok = await client.post(f"/api/v1/reservations/{a['reservation']['id']}/modify-dates", headers=manager_h, json={"check_in": future(10), "check_out": future(13)})
    assert ok.status_code == 200  # nothing was left half-claimed by the failed attempt


async def test_extra_guest_charge_and_taxes_and_promo(client, hotel, admin_h, db):
    await client.put("/api/v1/settings/taxes", headers=admin_h, json=[{"name": "Service charge", "rate_bp": 1000, "enabled": True}])
    await client.post("/api/v1/promotions", headers=admin_h, json={"title": "Ten off", "code": "ten", "discount_type": "percent", "value": 10, "status": "published"})
    body = {**stay(hotel, cat="exe"), "adults": 3, "promo_code": "TEN"}
    q = (await client.post("/api/v1/bookings/quote", json=body)).json()
    # 2 nights x 900 = 1800 accommodation; 1 extra guest x 100 x 2 nights = 200; discount 10% of accommodation = 180
    assert q["accommodation_minor"] == 180000 and q["extra_guest_minor"] == 20000 and q["discount"]["amount_minor"] == 18000
    assert q["subtotal_minor"] == 182000 and q["taxes"][0]["amount_minor"] == 18200 and q["total_minor"] == 200200
    assert (await client.post("/api/v1/bookings/quote", json={**body, "promo_code": "BOGUS"})).status_code == 400


async def test_pricing_rules_precedence(client, hotel, admin_h):
    cid = hotel["std"]["id"]
    d = future(10)
    await client.post("/api/v1/pricing/rules", headers=admin_h, json={"name": "Season", "type": "seasonal", "rate_minor": 60000, "category_id": cid, "start_date": future(8), "end_date": future(20)})
    await client.post("/api/v1/pricing/rules", headers=admin_h, json={"name": "Special day", "type": "date", "rate_minor": 99000, "category_id": cid, "start_date": d, "end_date": d})
    rates = {r["date"]: r["rate_minor"] for r in (await client.get(f"/api/v1/pricing/preview?category_id={cid}&start={future(7)}&days=6", headers=admin_h)).json()}
    assert rates[future(7)] == 50000 and rates[future(9)] == 60000 and rates[d] == 99000
    # invalid rule is rejected
    bad = await client.post("/api/v1/pricing/rules", headers=admin_h, json={"name": "x", "type": "seasonal", "rate_minor": 1000})
    assert bad.status_code == 422


async def test_bookings_are_private_to_email(client, hotel):
    r = (await book(client, hotel)).json()
    ok = await client.post("/api/v1/bookings/lookup", json={"reference": r["reference"], "email": "ama@example.com"})
    assert ok.status_code == 200 and ok.json()["reference"].startswith("NLH-")
    assert (await client.post("/api/v1/bookings/lookup", json={"reference": r["reference"], "email": "other@example.com"})).status_code == 404
    assert "internal_notes" not in ok.json()


async def test_negative_reservation_charge_is_rejected(client, hotel, manager_h, db):
    booking = (await book(client, hotel)).json()
    reservation = await db.reservations.find_one({"reference": booking["reference"]})
    response = await client.post(
        f"/api/v1/reservations/{reservation['_id']}/charges",
        headers=manager_h,
        json={"description": "Invalid adjustment", "amount_minor": -100},
    )
    assert response.status_code == 400
    assert await db.reservations.find_one({"_id": reservation["_id"]}) == reservation


async def test_guest_change_request_is_private_single_pending_and_staff_reviewed(client, hotel, db, recep_h, manager_h):
    booking = (await book(client, hotel)).json()
    payload = {"reference": booking["reference"], "email": "ama@example.com", "message": "Please add one extra guest"}
    request = await client.post("/api/v1/bookings/change-request", json=payload)
    assert request.status_code == 200 and request.json()["change_request"]["status"] == "pending"
    assert (await client.post("/api/v1/bookings/change-request", json={**payload, "email": "other@example.com"})).status_code == 404
    assert (await client.post("/api/v1/bookings/change-request", json=payload)).status_code == 409

    res = await db.reservations.find_one({"reference": booking["reference"]})
    path = f"/api/v1/reservations/{res['_id']}/review-change-request"
    assert (await client.post(path, headers=recep_h)).status_code == 403
    reviewed = await client.post(path, headers=manager_h)
    assert reviewed.status_code == 200 and reviewed.json()["change_request"]["status"] == "reviewed"
    assert (await client.post(path, headers=manager_h)).status_code == 409


async def test_unique_booking_references(client, hotel):
    refs = set()
    for i in range(5):
        r = await client.post("/api/v1/bookings", json={**stay(hotel, d_in=20 + i * 3, d_out=22 + i * 3), "guest": guest(f"u{i}@example.com")})
        refs.add(r.json()["reference"])
    assert len(refs) == 5
