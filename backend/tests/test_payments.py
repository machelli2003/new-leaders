import asyncio
import json
import re
from datetime import timedelta

import pytest
from fastapi import HTTPException

from app import utils
from app.services import finance
from .conftest import future, guest, sign, stay


async def new_booking(client, hotel, **kw):
    r = await client.post("/api/v1/bookings", json={**stay(hotel, **kw), "guest": guest()})
    assert r.status_code == 201, r.text
    return r.json()


async def pay(client, ref, option="full", email="ama@example.com"):
    r = await client.post("/api/v1/bookings/pay", json={"reference": ref, "email": email, "option": option})
    return r


async def webhook(client, body):
    raw, sig = sign(body)
    return await client.post("/api/v1/webhooks/paystack", content=raw, headers={"x-paystack-signature": sig, "content-type": "application/json"})


async def test_full_payment_flow_confirms_only_after_verification(client, hotel, gateway, db):
    b = await new_booking(client, hotel)
    assert b["status"] == "pending" and b["payment_status"] == "unpaid"
    p = await pay(client, b["reference"])
    assert p.status_code == 200
    pref = p.json()["reference"]
    assert re.fullmatch(r"NLHP\d{4}[0-9A-F]{32}", pref)
    assert p.json()["amount_minor"] == 100000
    # the guest lands on the success page BEFORE paying: browser redirect proves nothing
    s = (await client.get(f"/api/v1/bookings/payment-status/{pref}")).json()
    assert s["status"] == "pending" and s["reservation_status"] == "pending"
    gateway.pay(pref)
    s = (await client.get(f"/api/v1/bookings/payment-status/{pref}")).json()
    assert s["status"] == "success" and s["reservation_status"] == "confirmed"
    res = await db.reservations.find_one({"reference": b["reference"]})
    assert res["payment_status"] == "paid" and res["balance"] == 0 and res["hold_expires_at"] is None
    assert (await db.payments.find_one({"reference": pref}))["receipt_number"].startswith("RCT-")
    # inventory is now permanently held (no expiry on room nights)
    assert await db.room_nights.count_documents({"owner_id": res["_id"], "hold_expires_at": None}) == 2


async def test_amount_or_currency_mismatch_is_flagged_not_applied(client, hotel, gateway, db):
    b = await new_booking(client, hotel)
    pref = (await pay(client, b["reference"])).json()["reference"]
    gateway.pay(pref, amount=100)  # customer somehow paid less
    s = (await client.get(f"/api/v1/bookings/payment-status/{pref}")).json()
    assert s["status"] == "flagged" and s["reservation_status"] == "pending"
    b2 = await new_booking(client, hotel, d_in=30, d_out=31)
    p2 = (await pay(client, b2["reference"])).json()["reference"]
    gateway.pay(p2, currency="USD")
    assert (await client.get(f"/api/v1/bookings/payment-status/{p2}")).json()["status"] == "flagged"


async def test_failed_and_abandoned_payment_then_retry(client, hotel, gateway, db):
    b = await new_booking(client, hotel)
    p1 = (await pay(client, b["reference"])).json()["reference"]
    gateway.txs[p1]["status"] = "failed"
    assert (await client.get(f"/api/v1/bookings/payment-status/{p1}")).json()["status"] == "failed"
    res = await db.reservations.find_one({"reference": b["reference"]})
    assert res["payment_status"] == "failed" and res["status"] == "pending"
    p2 = (await pay(client, b["reference"])).json()["reference"]  # retry gets a fresh payment reference
    assert p2 != p1
    gateway.pay(p2)
    assert (await client.get(f"/api/v1/bookings/payment-status/{p2}")).json()["reservation_status"] == "confirmed"


async def test_abandoned_checkout_is_released_after_window(client, hotel, gateway, db):
    b = await new_booking(client, hotel)
    pref = (await pay(client, b["reference"])).json()["reference"]
    await db.payments.update_one({"reference": pref}, {"$set": {"created_at": utils.utcnow() - timedelta(minutes=45)}})
    s = (await client.get(f"/api/v1/bookings/payment-status/{pref}")).json()
    assert s["status"] == "abandoned"
    assert (await db.reservations.find_one({"reference": b["reference"]}))["payment_status"] == "failed"
    p2 = (await pay(client, b["reference"])).json()["reference"]  # guest can try again
    gateway.pay(p2)
    assert (await client.get(f"/api/v1/bookings/payment-status/{p2}")).json()["reservation_status"] == "confirmed"


async def test_invalid_reference_and_unconfigured(client, hotel, gateway):
    assert (await client.get("/api/v1/bookings/payment-status/NOPE")).status_code == 404
    b = await new_booking(client, hotel)
    gateway.fail_init = True
    assert (await pay(client, b["reference"])).status_code == 502
    assert (await pay(client, b["reference"], email="wrong@example.com")).status_code == 404


async def test_pay_at_hotel_booking_can_omit_email_and_be_found_by_phone(client, hotel, admin_h):
    settings = await client.put(
        "/api/v1/settings/payment",
        headers=admin_h,
        json={"require_full_payment": True, "deposit_enabled": False, "allow_pay_at_hotel": True},
    )
    assert settings.status_code == 200, settings.text
    payload = {
        **stay(hotel),
        "guest": {"name": "Ama Mensah", "phone": "+233200000000", "country": "Ghana"},
        "pay_at_hotel": True,
    }
    response = await client.post("/api/v1/bookings", json=payload)
    assert response.status_code == 201, response.text
    reference = response.json()["reference"]
    assert response.json()["guest"]["email"] is None

    found = await client.post("/api/v1/bookings/lookup", json={"reference": reference, "phone": "+233200000000"})
    assert found.status_code == 200, found.text
    assert found.json()["guest"]["phone"] == "+233200000000"
    wrong_contact = await client.post("/api/v1/bookings/lookup", json={"reference": reference, "phone": "0209999999"})
    assert wrong_contact.status_code == 404
    online_without_email = await client.post(
        "/api/v1/bookings",
        json={**payload, "pay_at_hotel": False},
    )
    assert online_without_email.status_code == 400


async def test_webhook_signature_required(client, hotel, gateway, db):
    b = await new_booking(client, hotel)
    pref = (await pay(client, b["reference"])).json()["reference"]
    gateway.pay(pref)
    body = {"event": "charge.success", "data": {"id": 1, "reference": pref}}
    raw = json.dumps(body).encode()
    assert (await client.post("/api/v1/webhooks/paystack", content=raw)).status_code == 401
    assert (await client.post("/api/v1/webhooks/paystack", content=raw, headers={"x-paystack-signature": "deadbeef"})).status_code == 401
    assert (await db.payments.find_one({"reference": pref}))["status"] == "pending"
    assert (await webhook(client, body)).status_code == 200
    assert (await db.payments.find_one({"reference": pref}))["status"] == "success"


async def test_duplicate_webhooks_do_not_duplicate_anything(client, hotel, gateway, db):
    b = await new_booking(client, hotel)
    pref = (await pay(client, b["reference"])).json()["reference"]
    gateway.pay(pref)
    body = {"event": "charge.success", "data": {"id": 55, "reference": pref}}
    results = [(await webhook(client, body)).json()["status"] for _ in range(4)]
    assert results[0] == "ok" and results[1:] == ["duplicate"] * 3
    assert await db.payments.count_documents({"reservation_reference": b["reference"]}) == 1
    assert await db.reservations.count_documents({"reference": b["reference"]}) == 1
    assert await db.payments.count_documents({"receipt_number": {"$exists": True}}) == 1
    emails = await db.notifications.count_documents({"channel": "email", "kind": "booking_confirmation"})
    assert emails == 1
    # even if the event bookkeeping were lost, settlement itself is idempotent
    await db.transactions.delete_many({})
    await webhook(client, body)
    assert await db.payments.count_documents({"receipt_number": {"$exists": True}}) == 1
    assert await db.notifications.count_documents({"channel": "email", "kind": "booking_confirmation"}) == 1


async def test_webhook_for_unknown_reference_is_harmless(client, hotel, db):
    r = await webhook(client, {"event": "charge.success", "data": {"id": 9, "reference": "UNKNOWN"}})
    assert r.status_code == 200
    assert await db.payments.count_documents({}) == 0


async def test_deposit_then_balance(client, hotel, gateway, admin_h, db):
    await client.put("/api/v1/settings/payment", headers=admin_h, json={"require_full_payment": False, "deposit_enabled": True, "deposit_type": "percent", "deposit_percent": 30})
    q = (await client.post("/api/v1/bookings/quote", json=stay(hotel))).json()
    assert q["payment_options"]["deposit"] == 30000 and q["confirm_threshold_minor"] == 30000
    b = await new_booking(client, hotel)
    p = (await pay(client, b["reference"], "deposit")).json()
    assert p["amount_minor"] == 30000
    gateway.pay(p["reference"])
    res = (await client.get(f"/api/v1/bookings/payment-status/{p['reference']}")).json()
    assert res["reservation_status"] == "confirmed"
    r = await db.reservations.find_one({"reference": b["reference"]})
    assert r["payment_status"] == "partially_paid" and r["balance"] == 70000
    look = (await client.post("/api/v1/bookings/lookup", json={"reference": b["reference"], "email": "ama@example.com"})).json()
    assert look["payment_options"]["full"] == 70000 and look["payment_options"]["deposit"] is None
    p2 = (await pay(client, b["reference"], "full")).json()
    assert p2["amount_minor"] == 70000
    gateway.pay(p2["reference"])
    await client.get(f"/api/v1/bookings/payment-status/{p2['reference']}")
    r = await db.reservations.find_one({"reference": b["reference"]})
    assert r["payment_status"] == "paid" and r["balance"] == 0
    # deposit option disappears when the hotel requires full payment
    await client.put("/api/v1/settings/payment", headers=admin_h, json={"require_full_payment": True, "deposit_enabled": True})
    b3 = await new_booking(client, hotel, d_in=40, d_out=41)
    assert (await pay(client, b3["reference"], "deposit")).status_code == 400


async def test_payment_after_hold_expiry_reclaims_or_flags(client, hotel, gateway, db):
    from app.services.reservations import expire_holds

    b = await new_booking(client, hotel, cat="exe")
    pref = (await pay(client, b["reference"])).json()["reference"]
    past = utils.utcnow() - timedelta(minutes=1)
    await db.reservations.update_many({}, {"$set": {"hold_expires_at": past}})
    await expire_holds(db)
    assert (await db.reservations.find_one({"reference": b["reference"]}))["status"] == "expired"
    gateway.pay(pref)  # money arrives after expiry, room still free -> re-secured and confirmed
    await client.get(f"/api/v1/bookings/payment-status/{pref}")
    assert (await db.reservations.find_one({"reference": b["reference"]}))["status"] == "confirmed"
    # second case: room got sold to someone else in the meantime -> flagged + refund requested
    b2 = await new_booking(client, hotel, cat="exe", d_in=50, d_out=52)
    p2 = (await pay(client, b2["reference"])).json()["reference"]
    await db.reservations.update_many({"reference": b2["reference"]}, {"$set": {"hold_expires_at": past}})
    await expire_holds(db)
    other = await client.post("/api/v1/bookings", json={**stay(hotel, cat="exe", d_in=50, d_out=52), "guest": guest("other@example.com")})
    assert other.status_code == 201
    gateway.pay(p2)
    await client.get(f"/api/v1/bookings/payment-status/{p2}")
    lost = await db.reservations.find_one({"reference": b2["reference"]})
    assert lost["status"] == "expired" and lost["needs_attention"] is True and lost["payment_status"] == "refund_pending"
    assert await db.refunds.count_documents({"reservation_reference": b2["reference"], "status": "requested"}) == 1


async def test_offline_payments_and_receipts(client, hotel, recep_h, manager_h):
    r = (await client.post("/api/v1/reservations", headers=recep_h, json={**stay(hotel), "guest": {"name": "Walk In", "phone": "0201112222"}})).json()
    rid = r["reservation"]["id"]
    p = await client.post("/api/v1/payments/offline", headers=recep_h, json={"reservation_id": rid, "amount_minor": 40000, "method": "cash", "idempotency_key": "payments-test-offline-0001"})
    assert p.status_code == 201 and p.json()["receipt_number"].startswith("RCT-")
    retry = await client.post("/api/v1/payments/offline", headers=recep_h, json={"reservation_id": rid, "amount_minor": 40000, "method": "cash", "idempotency_key": "payments-test-offline-0001"})
    assert retry.status_code == 201 and retry.json()["id"] == p.json()["id"]
    assert (await client.post("/api/v1/payments/offline", headers=recep_h, json={"reservation_id": rid, "amount_minor": 999999, "method": "cash", "idempotency_key": "payments-test-offline-0002"})).status_code == 400
    assert (await client.post("/api/v1/payments/offline", headers=manager_h, json={"reservation_id": rid, "amount_minor": 100, "method": "cash", "idempotency_key": "payments-test-offline-0003"})).status_code == 403
    p2 = await client.post("/api/v1/payments/offline", headers=recep_h, json={"reservation_id": rid, "amount_minor": 60000, "method": "mobile_money", "idempotency_key": "payments-test-offline-0004"})
    d = (await client.get(f"/api/v1/reservations/{rid}", headers=recep_h)).json()
    assert d["reservation"]["payment_status"] == "paid" and d["reservation"]["balance"] == 0 and len(d["payments"]) == 2


async def test_concurrent_offline_payments_cannot_overpay(client, hotel, recep_h, db):
    reservation = (await client.post(
        "/api/v1/reservations",
        headers=recep_h,
        json={**stay(hotel), "guest": {"name": "Concurrency Guest", "phone": "0201112222"}},
    )).json()["reservation"]
    bodies = [
        {"reservation_id": reservation["id"], "amount_minor": 60000, "method": "cash", "idempotency_key": f"offline-race-key-{i:04d}"}
        for i in range(2)
    ]
    responses = await asyncio.gather(*[
        client.post("/api/v1/payments/offline", headers=recep_h, json=body)
        for body in bodies
    ])

    assert sorted(response.status_code for response in responses) == [201, 400]
    saved = await db.reservations.find_one({"_id": reservation["id"]})
    payments = await db.payments.find({"reservation_id": reservation["id"], "status": "success"}).to_list(None)
    assert saved["amount_paid"] == 60000
    assert saved["balance"] == 40000
    assert sum(payment["amount"] for payment in payments) == 60000


async def test_cancellation_policy_and_refund_flow(client, hotel, gateway, admin_h, manager_h, super_h, db):
    await client.put("/api/v1/settings/cancellation", headers=admin_h, json={"free_cancellation_hours": 48, "late_fee_percent": 50, "non_refundable": False})
    # booking far in the future -> free cancellation -> full refund requested (never automatic)
    b = await new_booking(client, hotel, d_in=20, d_out=22)
    pref = (await pay(client, b["reference"])).json()["reference"]
    gateway.pay(pref)
    await client.get(f"/api/v1/bookings/payment-status/{pref}")
    prev = (await client.post("/api/v1/bookings/cancel-preview", json={"reference": b["reference"], "email": "ama@example.com"})).json()
    assert prev["free_cancellation"] is True and prev["refundable_minor"] == 100000
    req = await client.post("/api/v1/bookings/cancel-request", json={"reference": b["reference"], "email": "ama@example.com", "reason": "plans changed"})
    assert req.json()["status"] == "cancellation_requested"
    rid = (await db.reservations.find_one({"reference": b["reference"]}))["_id"]
    assert await db.room_nights.count_documents({"owner_id": rid}) == 2  # rooms stay held until staff decide
    done = await client.post(f"/api/v1/reservations/{rid}/cancel", headers=manager_h, json={"reason": "approved"})
    assert done.status_code == 200 and done.json()["status"] == "cancelled"
    assert await db.room_nights.count_documents({"owner_id": rid}) == 0
    refunds = (await client.get("/api/v1/refunds", headers=admin_h)).json()["items"]
    assert len(refunds) == 1 and refunds[0]["amount"] == 100000 and refunds[0]["status"] == "requested"
    assert (await db.reservations.find_one({"_id": rid}))["payment_status"] == "refund_pending"
    # The requester cannot approve, and approver and processor must be distinct.
    fid = refunds[0]["id"]
    assert (await client.post(f"/api/v1/refunds/{fid}/process", headers=manager_h, json={})).status_code == 403
    assert (await client.post(f"/api/v1/refunds/{fid}/approve", headers=manager_h, json={})).status_code == 403
    approved = await client.post(f"/api/v1/refunds/{fid}/approve", headers=admin_h, json={})
    assert approved.status_code == 200 and approved.json()["approved_by"]
    assert (await client.post(f"/api/v1/refunds/{fid}/process", headers=admin_h, json={})).status_code == 403
    pr = await client.post(f"/api/v1/refunds/{fid}/process", headers=super_h, json={})
    assert pr.status_code == 200 and pr.json()["status"] == "processing"
    assert gateway.refunds == [{"transaction": pref, "amount": 100000}]
    # Paystack confirms via webhook -> processed -> refunded
    await webhook(client, {"event": "refund.processed", "data": {"id": 987654, "transaction_reference": pref}})
    r = await db.reservations.find_one({"_id": rid})
    assert r["payment_status"] == "refunded" and r["amount_paid"] == 0
    assert (await client.post(f"/api/v1/refunds/{fid}/process", headers=super_h, json={})).status_code == 409  # no double refund


async def test_refund_requester_cannot_approve_or_process(client, hotel, gateway, admin_h, super_h, db):
    booking = await new_booking(client, hotel)
    payment_reference = (await pay(client, booking["reference"])).json()["reference"]
    gateway.pay(payment_reference)
    await client.get(f"/api/v1/bookings/payment-status/{payment_reference}")
    reservation = await db.reservations.find_one({"reference": booking["reference"]})
    requested = await client.post(
        "/api/v1/refunds",
        headers=admin_h,
        json={"reservation_id": reservation["_id"], "amount_minor": 100000, "reason": "Guest refund request"},
    )
    assert requested.status_code == 201
    refund_id = requested.json()[0]["id"]

    assert (await client.post(f"/api/v1/refunds/{refund_id}/approve", headers=admin_h, json={})).status_code == 403
    approved = await client.post(f"/api/v1/refunds/{refund_id}/approve", headers=super_h, json={})
    assert approved.status_code == 200
    assert (await client.post(f"/api/v1/refunds/{refund_id}/process", headers=super_h, json={})).status_code == 403


async def test_concurrent_refund_processing_submits_once(client, hotel, gateway, admin_h, super_h, db):
    booking = await new_booking(client, hotel)
    payment_reference = (await pay(client, booking["reference"])).json()["reference"]
    gateway.pay(payment_reference)
    await client.get(f"/api/v1/bookings/payment-status/{payment_reference}")
    reservation = await db.reservations.find_one({"reference": booking["reference"]})
    payment = await db.payments.find_one({"reference": payment_reference})
    refund = (await finance.request_refund(
        db, reservation, payment["amount"], "guest request", None, payment_id=payment["_id"],
    ))[0]
    approver = await db.users.find_one({"role": "hotel_admin"})
    actor = await db.users.find_one({"role": "super_admin"})
    await db.refunds.update_one(
        {"_id": refund["_id"]},
        {"$set": {"status": "approved", "approved_by": approver["_id"]}},
    )
    refund["status"] = "approved"
    refund["approved_by"] = approver["_id"]

    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def slow_refund(**kwargs):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return {"id": 987654, "status": "pending"}

    gateway.refund = slow_refund
    first = asyncio.create_task(finance.process_refund(db, refund, actor))
    await asyncio.wait_for(started.wait(), timeout=2)
    with pytest.raises(HTTPException) as rejected:
        await finance.process_refund(db, refund, actor)
    assert rejected.value.status_code == 409
    release.set()
    result = await first
    assert calls == 1
    assert result["status"] == "processing"


async def test_late_cancellation_fee_and_override_permission(client, hotel, admin_h, manager_h, recep_h, db):
    await client.put("/api/v1/settings/cancellation", headers=admin_h, json={"free_cancellation_hours": 48, "late_fee_percent": 50, "non_refundable": False})
    r = (await client.post("/api/v1/reservations", headers=recep_h, json={**stay(hotel, d_in=1, d_out=3), "guest": {"name": "Late Guest", "phone": "0201112299"}})).json()
    rid = r["reservation"]["id"]
    await client.post("/api/v1/payments/offline", headers=recep_h, json={"reservation_id": rid, "amount_minor": 100000, "method": "cash", "idempotency_key": "payments-test-offline-0005"})
    assert (await client.post(f"/api/v1/reservations/{rid}/cancel", headers=manager_h, json={"waive_fee": True})).status_code == 403
    c = await client.post(f"/api/v1/reservations/{rid}/cancel", headers=manager_h, json={"reason": "late"})
    cancel = c.json()["cancellation"]
    assert cancel["fee_minor"] == 50000 and cancel["refundable_minor"] == 50000
    assert (await client.get("/api/v1/refunds", headers=admin_h)).json()["items"][0]["amount"] == 50000


async def test_refund_cannot_exceed_paid(client, hotel, admin_h, recep_h):
    r = (await client.post("/api/v1/reservations", headers=recep_h, json={**stay(hotel), "guest": {"name": "Over Refund", "phone": "0201112288"}})).json()
    rid = r["reservation"]["id"]
    await client.post("/api/v1/payments/offline", headers=recep_h, json={"reservation_id": rid, "amount_minor": 10000, "method": "cash", "idempotency_key": "payments-test-offline-0006"})
    assert (await client.post("/api/v1/refunds", headers=admin_h, json={"reservation_id": rid, "amount_minor": 20000, "reason": "too much"})).status_code == 400
    assert (await client.post("/api/v1/refunds", headers=admin_h, json={"reservation_id": rid, "amount_minor": 10000, "reason": "okay"})).status_code == 201
