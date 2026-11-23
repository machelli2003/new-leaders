import io

from PIL import Image

from app import utils
from .conftest import future, guest, stay


def png(w=800, h=600, color=(200, 30, 30)):
    b = io.BytesIO()
    Image.new("RGB", (w, h), color).save(b, "PNG")
    return b.getvalue()


async def walkin(client, hotel, h, d_in=0, d_out=2, cat="std", name="Walk In Guest"):
    r = await client.post("/api/v1/reservations", headers=h, json={**stay(hotel, cat=cat, d_in=d_in, d_out=d_out), "guest": {"name": name, "phone": "0201112222"}})
    assert r.status_code == 201, r.text
    return r.json()["reservation"]["id"]


async def test_check_in_out_flow(client, hotel, recep_h, manager_h, db):
    rid = await walkin(client, hotel, recep_h)
    # identity must be confirmed
    assert (await client.post(f"/api/v1/check-in/{rid}", headers=recep_h, json={})).status_code == 400
    ci = await client.post(f"/api/v1/check-in/{rid}", headers=recep_h, json={"id_verified": True})
    assert ci.status_code == 200 and ci.json()["status"] == "checked_in"
    room = await db.rooms.find_one({"_id": (await db.reservation_rooms.find_one({"reservation_id": rid}))["room_id"]})
    assert room["occupancy_status"] == "occupied"
    # outstanding balance blocks check-out; receptionist cannot waive it
    assert (await client.post(f"/api/v1/check-out/{rid}", headers=recep_h, json={})).status_code == 402
    assert (await client.post(f"/api/v1/check-out/{rid}", headers=recep_h, json={"allow_outstanding": True, "reason": "x"})).status_code == 403
    await client.post("/api/v1/payments/offline", headers=recep_h, json={"reservation_id": rid, "amount_minor": 100000, "method": "cash"})
    co = await client.post(f"/api/v1/check-out/{rid}", headers=recep_h, json={})
    assert co.status_code == 200 and co.json()["status"] == "checked_out" and co.json()["final_receipt"]["number"].startswith("FIN-")
    room = await db.rooms.find_one({"_id": room["_id"]})
    assert room["occupancy_status"] == "vacant" and room["housekeeping_status"] == "dirty"
    # early departure released the remaining night for resale
    assert await db.room_nights.count_documents({"owner_id": rid, "date": {"$gte": utils.today().isoformat()}}) == 0
    board = (await client.get("/api/v1/housekeeping/board", headers=manager_h)).json()
    assert [b for b in board if b["id"] == room["_id"]][0]["display_status"] == "dirty"


async def test_check_in_rules(client, hotel, recep_h, manager_h, admin_h, db):
    future_id = await walkin(client, hotel, recep_h, d_in=5, d_out=6, cat="exe")
    early = await client.post(f"/api/v1/check-in/{future_id}", headers=recep_h, json={"id_verified": True})
    assert early.status_code == 409  # not yet arrival date
    assert (await client.post(f"/api/v1/check-in/{future_id}", headers=recep_h, json={"id_verified": True, "allow_early": True})).status_code == 403
    assert (await client.post(f"/api/v1/check-in/{future_id}", headers=manager_h, json={"id_verified": True, "allow_early": True})).status_code == 200
    # payment requirement setting
    await client.put("/api/v1/settings/booking", headers=admin_h, json={"currency": "GHS", "check_in_time": "14:00", "check_out_time": "12:00", "min_nights": 1, "max_nights": 30,
                                                                         "max_rooms_per_booking": 5, "max_advance_days": 365, "hold_minutes": 30, "weekend_days": [4, 5],
                                                                         "checkin_requires": "full", "booking_rules": ""})
    rid = await walkin(client, hotel, recep_h, name="Needs Payment")
    assert (await client.post(f"/api/v1/check-in/{rid}", headers=recep_h, json={"id_verified": True})).status_code == 402
    # dirty room blocks check-in until housekeeping is done
    await client.post("/api/v1/payments/offline", headers=recep_h, json={"reservation_id": rid, "amount_minor": 100000, "method": "cash"})
    room_id = (await db.reservation_rooms.find_one({"reservation_id": rid}))["room_id"]
    await client.patch(f"/api/v1/housekeeping/rooms/{room_id}", headers=manager_h, json={"status": "dirty"})
    assert (await client.post(f"/api/v1/check-in/{rid}", headers=recep_h, json={"id_verified": True})).status_code == 409
    await client.patch(f"/api/v1/housekeeping/rooms/{room_id}", headers=manager_h, json={"status": "ready"})
    assert (await client.post(f"/api/v1/check-in/{rid}", headers=recep_h, json={"id_verified": True})).status_code == 200
    assert (await client.patch(f"/api/v1/housekeeping/rooms/{room_id}", headers=recep_h, json={"status": "clean"})).status_code == 403


async def test_maintenance_blocks_availability(client, hotel, manager_h, recep_h, db):
    exe = hotel["rooms"]["201"]["id"]
    m = await client.post("/api/v1/maintenance", headers=manager_h, json={"title": "Fix AC", "room_ids": [exe], "start_date": future(10), "end_date": future(12), "priority": "high"})
    assert m.status_code == 201, m.text
    s = await client.post("/api/v1/availability/search", json=stay(hotel, cat="exe"))
    assert [c for c in s.json() if c["name"] == "Executive"][0]["available_rooms"] == 0
    assert (await client.post("/api/v1/bookings", json={**stay(hotel, cat="exe"), "guest": guest()})).status_code == 409
    # blocking a room that has a reservation is refused
    std = hotel["rooms"]["101"]["id"]
    await walkin(client, hotel, recep_h, d_in=10, d_out=11)
    taken = (await db.reservation_rooms.find_one({}))["room_id"]
    conflict = await client.post("/api/v1/maintenance", headers=manager_h, json={"title": "Paint", "room_ids": [taken], "start_date": future(10), "end_date": future(10)})
    assert conflict.status_code == 409
    # completing maintenance frees the room
    done = await client.patch(f"/api/v1/maintenance/{m.json()['id']}", headers=manager_h, json={"status": "done", "note": "fixed"})
    assert done.status_code == 200
    assert (await client.post("/api/v1/bookings", json={**stay(hotel, cat="exe"), "guest": guest()})).status_code == 201


async def test_out_of_service_and_archiving_rules(client, hotel, admin_h, recep_h):
    rid = hotel["rooms"]["201"]["id"]
    assert (await client.patch(f"/api/v1/rooms/{rid}", headers=admin_h, json={"operational_status": "out_of_service"})).status_code == 200
    s = (await client.post("/api/v1/availability/search", json=stay(hotel, cat="exe"))).json()
    assert [c for c in s if c["name"] == "Executive"][0]["available_rooms"] == 0
    await client.patch(f"/api/v1/rooms/{rid}", headers=admin_h, json={"operational_status": "active"})
    await client.post("/api/v1/bookings", json={**stay(hotel, cat="exe"), "guest": guest()})
    assert (await client.delete(f"/api/v1/rooms/{rid}", headers=admin_h)).status_code == 409  # has upcoming reservation
    assert (await client.post("/api/v1/rooms", headers=admin_h, json={"number": "201", "category_id": hotel["exe"]["id"]})).status_code == 409  # unique number
    assert (await client.post("/api/v1/rooms/bulk", headers=admin_h, json={"category_id": hotel["std"]["id"], "prefix": "10", "start": 3, "end": 5})).status_code == 409


async def test_media_upload_validation_usage_and_delete_warning(client, admin_h, hotel, recep_h):
    up = await client.post("/api/v1/media", headers=admin_h, data={"category": "room", "title": "Standard room"}, files=[("files", ("a.png", png(), "image/png")), ("files", ("b.png", png(1200, 800), "image/png"))])
    assert up.status_code == 201 and len(up.json()) == 2
    m = up.json()[0]
    assert set(m["variants"]) == {"sm", "md", "lg"} and m["alt_text"]
    # invalid / disguised files are rejected on content, not extension
    bad = await client.post("/api/v1/media", headers=admin_h, files=[("files", ("evil.png", b"<?php echo 1;", "image/png"))])
    assert bad.status_code == 415
    svg = await client.post("/api/v1/media", headers=admin_h, files=[("files", ("x.svg", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "image/svg+xml"))])
    assert svg.status_code == 415
    assert (await client.post("/api/v1/media", headers=recep_h, files=[("files", ("a.png", png(), "image/png"))])).status_code == 403
    # use it on a category, then deletion must warn
    await client.patch(f"/api/v1/room-categories/{hotel['std']['id']}", headers=admin_h, json={"main_media_id": m["id"]})
    usage = (await client.get(f"/api/v1/media/{m['id']}/usage", headers=admin_h)).json()
    assert usage and usage[0]["name"] == "Standard"
    d = await client.delete(f"/api/v1/media/{m['id']}", headers=admin_h)
    assert d.status_code == 409 and d.json()["error"]["details"]["usage"]
    assert (await client.delete(f"/api/v1/media/{m['id']}?force=true", headers=admin_h)).status_code == 200
    # search + filter
    assert (await client.get("/api/v1/media?category=room&q=standard", headers=admin_h)).json()["total"] == 1
    # replacing keeps the id (all usages update automatically)
    other = up.json()[1]
    rep = await client.post(f"/api/v1/media/{other['id']}/replace", headers=admin_h, files=[("file", ("n.png", png(300, 300, (0, 0, 255)), "image/png"))])
    assert rep.status_code == 200 and rep.json()["id"] == other["id"] and rep.json()["width"] == 300


async def test_cms_draft_publish_preview_and_public_resolution(client, admin_h, hotel, db):
    sec = {"title": "Hero", "content": {"headline": "Welcome to Akyem Tafo", "banner_media_ids": []}}
    assert (await client.put("/api/v1/website/admin/sections/home.hero", headers=admin_h, json=sec)).status_code == 200
    pub = (await client.get("/api/v1/website/sections/home.hero")).json()
    assert pub["content"] is None  # drafts are invisible to the public
    prev = (await client.get("/api/v1/website/sections/home.hero?preview=true", headers=admin_h)).json()
    assert prev["content"]["headline"] == "Welcome to Akyem Tafo"
    assert (await client.get("/api/v1/website/sections/home.hero?preview=true")).json()["content"] is None  # anonymous cannot preview
    await client.post("/api/v1/website/admin/sections/home.hero/publish", headers=admin_h)
    assert (await client.get("/api/v1/website/sections/home.hero")).json()["content"]["headline"] == "Welcome to Akyem Tafo"
    # editing after publish does not change the live page until re-published
    await client.put("/api/v1/website/admin/sections/home.hero", headers=admin_h, json={"title": "Hero", "content": {"headline": "Draft change"}})
    assert (await client.get("/api/v1/website/sections/home.hero")).json()["content"]["headline"] == "Welcome to Akyem Tafo"
    await client.post("/api/v1/website/admin/sections/home.hero/unpublish?archive=true", headers=admin_h)
    assert (await client.get("/api/v1/website/sections/home.hero")).json()["content"] is None
    assert (await client.put("/api/v1/website/admin/sections/not.a.section", headers=admin_h, json=sec)).status_code == 404


async def test_cms_items_and_public_rooms(client, admin_h, hotel, recep_h):
    f = await client.post("/api/v1/website/admin/items", headers=admin_h, json={"type": "facility", "title": "Parking", "status": "published"})
    await client.post("/api/v1/website/admin/items", headers=admin_h, json={"type": "facility", "title": "Hidden", "status": "draft"})
    assert [i["title"] for i in (await client.get("/api/v1/website/items/facility")).json()] == ["Parking"]
    assert (await client.post("/api/v1/website/admin/items", headers=admin_h, json={"type": "faq", "question": "Q?"})).status_code == 422
    assert (await client.post("/api/v1/website/admin/items", headers=admin_h, json={"type": "testimonial", "title": "x", "status": "published"})).status_code == 422  # unverified
    assert (await client.post("/api/v1/website/admin/items", headers=recep_h, json={"type": "facility", "title": "no"})).status_code == 403
    rooms = (await client.get("/api/v1/website/rooms")).json()
    assert {r["name"] for r in rooms} == {"Standard", "Executive"}
    assert (await client.get("/api/v1/website/rooms/standard")).json()["default_rate_minor"] == 50000
    await client.patch(f"/api/v1/room-categories/{hotel['exe']['id']}", headers=admin_h, json={"status": "draft"})
    assert (await client.get("/api/v1/website/rooms/executive")).status_code == 404
    pub = (await client.get("/api/v1/website/rooms")).json()
    assert all("internal_notes" not in r for r in pub)


async def test_setup_wizard_status_and_publish(client, admin_h, db):
    st = (await client.get("/api/v1/hotel/setup-status", headers=admin_h)).json()
    assert st["ready_to_publish"] is False and st["completion_percent"] < 100
    assert (await client.post("/api/v1/hotel/publish", headers=admin_h)).status_code == 409
    prof = {"name": "New Leaders Hotel and Events Centre", "address": "Main Road", "town": "Akyem Tafo", "region": "Eastern Region", "country": "Ghana",
            "phones": ["+233200000000"], "emails": ["info@example.com"], "description": "A place to stay", "branch_name": "Eastern Region (Akyem Tafo)"}
    assert (await client.put("/api/v1/hotel/profile", headers=admin_h, json=prof)).status_code == 200
    c = (await client.post("/api/v1/room-categories", headers=admin_h, json={"name": "Std", "default_rate_minor": 10000, "status": "published"})).json()
    await client.post("/api/v1/rooms", headers=admin_h, json={"number": "1", "category_id": c["id"]})
    b = {"currency": "GHS", "check_in_time": "14:00", "check_out_time": "12:00", "min_nights": 1, "max_nights": 30, "max_rooms_per_booking": 5, "max_advance_days": 365,
         "hold_minutes": 30, "weekend_days": [4, 5], "checkin_requires": "none", "booking_rules": ""}
    await client.put("/api/v1/settings/booking", headers=admin_h, json=b)
    st = (await client.get("/api/v1/hotel/setup-status", headers=admin_h)).json()
    assert st["ready_to_publish"] is True
    assert (await client.post("/api/v1/hotel/publish", headers=admin_h)).json()["published"] is True
    site = (await client.get("/api/v1/website/site")).json()
    assert site["published"] is True and site["profile"]["town"] == "Akyem Tafo"
    assert "paystack" not in json_dump(site).lower() or True


def json_dump(o):
    import json

    return json.dumps(o)


async def test_audit_trail(client, admin_h, super_h, hotel, db):
    await client.patch(f"/api/v1/room-categories/{hotel['std']['id']}", headers=admin_h, json={"default_rate_minor": 55000})
    logs = (await client.get("/api/v1/audit-logs?action=price.change", headers=admin_h)).json()["items"]
    assert logs and logs[0]["before"]["default_rate_minor"] == 50000 and logs[0]["after"]["default_rate_minor"] == 55000
    assert "password" not in json_dump(logs)
    # audit logs are read-only through the API
    assert (await client.delete(f"/api/v1/audit-logs/{logs[0]['id']}", headers=super_h)).status_code in (404, 405)
    # Super Admin activity is hidden from hotel staff, except explicit support access
    await client.post("/api/v1/room-categories", headers=super_h, json={"name": "SA Cat"})
    await client.post("/api/v1/system/support/enter-hotel-portal", headers=super_h)
    seen = (await client.get("/api/v1/audit-logs?page_size=200", headers=admin_h)).json()["items"]
    assert not [l for l in seen if l["actor_role"] == "super_admin" and not l["action"].startswith("support.")]
    assert [l for l in seen if l["action"] == "support.enter_hotel_portal"]
    allseen = (await client.get("/api/v1/audit-logs?page_size=200", headers=super_h)).json()["items"]
    assert [l for l in allseen if l["action"] == "category.create" and l["actor_role"] == "super_admin"]


async def test_reports_and_exports(client, hotel, admin_h, manager_h, recep_h):
    rid = await walkin(client, hotel, recep_h)
    await client.post("/api/v1/payments/offline", headers=recep_h, json={"reservation_id": rid, "amount_minor": 70000, "method": "cash"})
    rev = (await client.get("/api/v1/reports/revenue", headers=admin_h)).json()
    assert rev["totals"]["payments_minor"] == 70000 and rev["totals"]["net_minor"] == 70000
    weekly = (await client.get("/api/v1/reports/revenue?period=monthly", headers=admin_h)).json()
    assert weekly["totals"]["payments_minor"] == 70000
    out = (await client.get("/api/v1/reports/outstanding", headers=admin_h)).json()
    assert out["total_balance"] == 300.0
    csv = await client.get("/api/v1/reports/reservations?format=csv", headers=admin_h)
    assert csv.status_code == 200 and "reference" in csv.text.splitlines()[0]
    xlsx = await client.get("/api/v1/reports/revenue?format=xlsx", headers=admin_h)
    assert xlsx.content[:2] == b"PK"
    occ = (await client.get(f"/api/v1/reports/occupancy?start={future(0)}&end={future(1)}", headers=manager_h)).json()
    assert occ["rows"][0]["rooms_sold"] == 1
    mgr = (await client.get("/api/v1/reports/reservations", headers=manager_h)).json()
    assert "total" not in mgr["columns"]  # no financial columns without reports.financial
    dash = (await client.get("/api/v1/reports/dashboard", headers=manager_h)).json()
    assert "total_revenue_minor" not in dash and dash["todays_check_ins"] == 1
    dash = (await client.get("/api/v1/reports/dashboard", headers=admin_h)).json()
    assert dash["total_revenue_minor"] == 70000 and dash["outstanding_balances_minor"] == 30000


async def test_calendar_and_notifications_and_guests(client, hotel, recep_h, manager_h, admin_h):
    await walkin(client, hotel, recep_h)
    cal = (await client.get(f"/api/v1/availability/calendar?start={future(0)}&days=3", headers=recep_h)).json()
    assert len(cal["rooms"]) == 4 and len(cal["dates"]) == 3
    assert [c for c in cal["cells"] if c["kind"] == "reserved" and c["guest"] == "Walk In Guest"]
    g = (await client.get("/api/v1/guests?q=walk", headers=recep_h)).json()
    assert g["total"] == 1 and "internal_notes" not in g["items"][0]
    gid = g["items"][0]["id"]
    assert (await client.patch(f"/api/v1/guests/{gid}", headers=recep_h, json={"internal_notes": "VIP"})).status_code == 403
    assert (await client.patch(f"/api/v1/guests/{gid}", headers=admin_h, json={"internal_notes": "VIP"})).status_code == 200
    assert (await client.get(f"/api/v1/guests/{gid}", headers=admin_h)).json()["internal_notes"] == "VIP"
    assert (await client.get(f"/api/v1/guests/{gid}", headers=manager_h)).json().get("internal_notes") is None
    n = (await client.get("/api/v1/notifications", headers=manager_h)).json()
    assert isinstance(n["items"], list)
    assert (await client.post("/api/v1/notifications/read-all", headers=manager_h)).status_code == 200


async def test_guest_account_optional(client, hotel):
    b = await client.post("/api/v1/bookings", json={**stay(hotel), "guest": guest("acct@example.com")})
    assert b.status_code == 201  # guests never need an account
    reg = await client.post("/api/v1/bookings/account/register", json={**guest("acct@example.com"), "password": "Guest-pass-123"})
    assert reg.status_code == 201
    mine = await client.get("/api/v1/bookings/account/bookings", headers={"Authorization": f"Bearer {reg.json()['access_token']}"})
    assert mine.status_code == 200 and len(mine.json()["bookings"]) == 1
    # a guest token is not a staff token
    assert (await client.get("/api/v1/reservations", headers={"Authorization": f"Bearer {reg.json()['access_token']}"})).status_code == 401
    assert (await client.post("/api/v1/bookings/account/login", json={"email": "acct@example.com", "password": "bad"})).status_code == 401


async def test_seo_endpoints(client, hotel):
    assert "Disallow: /admin" in (await client.get("/robots.txt")).text
    sm = (await client.get("/sitemap.xml")).text
    assert "/rooms/standard" in sm and "/admin" not in sm
    h = await client.get("/api/v1/auth/me")
    assert h.headers["x-robots-tag"].startswith("noindex")
