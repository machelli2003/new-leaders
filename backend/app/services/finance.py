"""Payments, balances and refunds. Reservation status and payment status are tracked separately."""
from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from ..audit import audit
from ..config import get_config
from ..hotel_settings import get_settings
from ..postgres_store import ReturnDocument
from ..utils import new_id, today, utcnow
from . import paystack
from .notify import notify_guest, notify_staff
from .pricing import payment_options


async def next_counter(db, name: str) -> int:
    doc = await db.counters.find_one_and_update(
        {"_id": name}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER
    )
    return int(doc["seq"])


async def recompute(db, reservation_id: str) -> dict:
    res = await db.reservations.find_one({"_id": reservation_id})
    payments = await db.payments.find({"reservation_id": reservation_id}).to_list(None)
    refunds = await db.refunds.find({"reservation_id": reservation_id}).to_list(None)
    paid = sum(p["amount"] for p in payments if p["status"] == "success")
    refunded = sum(r["amount"] for r in refunds if r["status"] == "processed")
    pending_refund = sum(r["amount"] for r in refunds if r["status"] in ("requested", "approved", "processing"))
    pending = any(p["status"] == "pending" for p in payments)
    failed = any(p["status"] in ("failed", "abandoned") for p in payments)
    charges = sum(c["amount_minor"] for c in res.get("charges", []))
    total = res["pricing"]["total_minor"] + charges
    net = paid - refunded
    if pending_refund > 0:
        ps = "refund_pending"
    elif refunded > 0:
        ps = "refunded" if net <= 0 else "partially_refunded"
    elif paid <= 0:
        ps = "pending" if pending else ("failed" if failed else "unpaid")
    elif net >= total:
        ps = "paid"
    else:
        ps = "partially_paid"
    closed = res["status"] in ("cancelled", "expired", "no_show")
    balance = 0 if closed else max(total - net, 0)
    upd = {"total_amount": total, "amount_paid": net, "balance": balance, "payment_status": ps, "updated_at": utcnow()}
    await db.reservations.update_one({"_id": reservation_id}, {"$set": upd})
    res.update(upd)
    return res


async def _receipt(db, payment_id: str) -> None:
    seq = await next_counter(db, f"receipt-{today().year}")
    await db.payments.update_one({"_id": payment_id}, {"$set": {"receipt_number": f"RCT-{today().year}-{seq:06d}"}})


async def after_success(db, payment: dict, user: dict | None = None) -> dict:
    """Common post-processing once a payment is recorded as successful (idempotent callers only)."""
    from .reservations import confirm_reservation  # local import: avoid cycle

    res = await recompute(db, payment["reservation_id"])
    was_pending = res["status"] in ("pending", "expired")  # money can arrive after a hold lapsed
    confirmed = False
    if was_pending and res["amount_paid"] >= res.get("confirm_threshold", res["total_amount"]):
        confirmed = await confirm_reservation(db, res["_id"], user)
        res = await recompute(db, res["_id"])
        if not confirmed:
            await db.reservations.update_one(
                {"_id": res["_id"]},
                {"$set": {"needs_attention": True, "attention_reason": "Payment received but rooms could not be re-secured. Refund or rebook."}},
            )
            await request_refund(db, res, payment["amount"], "Rooms no longer available after payment", None, payment_id=payment["_id"])
            await notify_staff(db, "attention", f"Action needed: payment received for lost inventory ({res['reference']})",
                               "Customer paid but the hold had expired and rooms were taken. A refund was requested.",
                               f"/admin/reservations/{res['_id']}", "reservations.view", email=True)
            return await recompute(db, res["_id"])
    await notify_staff(db, "payment", f"Payment received – {res['reference']}",
                       f"{payment['amount'] / 100:,.2f} {payment['currency']} via {payment['method']}",
                       f"/admin/reservations/{res['_id']}", "payments.view")
    if confirmed:
        await notify_guest(db, "booking_confirmation", res)
        await notify_staff(db, "reservation", f"New reservation {res['reference']}", f"{res['guest'].get('name')} · {res['check_in']} → {res['check_out']}",
                           f"/admin/reservations/{res['_id']}", "reservations.view", email=True)
    else:
        await notify_guest(db, "deposit_receipt" if res["balance"] > 0 else "payment_confirmation", res)
    return res


# ---------------- online (Paystack) ----------------
async def init_online_payment(db, res: dict, option: str) -> dict:
    cfg = get_config()
    settings = await get_settings(db)
    if res["status"] not in ("pending", "confirmed", "checked_in"):
        raise HTTPException(409, "This booking can no longer accept payment")
    now = utcnow()
    if res["status"] == "pending" and (not res.get("hold_expires_at") or res["hold_expires_at"] < now):
        raise HTTPException(409, "Your room hold has expired. Please start a new booking.")
    opts = payment_options(res["total_amount"], res["amount_paid"], settings["payment"])
    amount = opts["deposit"] if option == "deposit" else opts["full"]
    if not amount or amount <= 0:
        raise HTTPException(400, "That payment option is not available for this booking")
    if not (res.get("guest") or {}).get("email"):
        raise HTTPException(400, "An email address is required for online payment")
    kind = "deposit" if option == "deposit" else ("full" if res["amount_paid"] == 0 else "balance")
    if res["status"] == "pending":  # give the guest time to finish paying
        new_exp = max(res["hold_expires_at"], now + timedelta(minutes=15))
        await db.reservations.update_one({"_id": res["_id"]}, {"$set": {"hold_expires_at": new_exp}})
        await db.room_nights.update_many({"owner_id": res["_id"], "hold_expires_at": {"$ne": None}}, {"$set": {"hold_expires_at": new_exp}})
    payment = {
        "_id": new_id(), "reservation_id": res["_id"], "reservation_reference": res["reference"],
        "reference": f"NLHP{today().year}{secrets.token_hex(6).upper()}", "amount": amount,
        "currency": settings["booking"]["currency"], "method": "paystack", "kind": kind, "status": "pending",
        "created_at": now, "updated_at": now, "recorded_by": None,
    }
    await db.payments.insert_one(payment)
    try:
        data = await paystack.get_client().initialize(
            email=res["guest"]["email"], amount=amount, reference=payment["reference"],
            callback_url=f"{cfg.public_base_url.rstrip('/')}/booking/payment/success",
            currency=payment["currency"], channels=settings["payment"].get("channels") or None,
            metadata={"reservation": res["reference"], "payment_id": payment["_id"]},
        )
    except paystack.PaystackNotConfigured:
        await db.payments.update_one({"_id": payment["_id"]}, {"$set": {"status": "failed", "failure": "gateway not configured"}})
        await recompute(db, res["_id"])
        raise HTTPException(503, "Online payment is not available right now. Please contact the hotel.")
    except paystack.PaystackError as e:
        await db.payments.update_one({"_id": payment["_id"]}, {"$set": {"status": "failed", "failure": str(e)[:200]}})
        await recompute(db, res["_id"])
        raise HTTPException(502, "We could not start the payment. Please try again.")
    await db.payments.update_one({"_id": payment["_id"]}, {"$set": {"access_code": data.get("access_code")}})
    await recompute(db, res["_id"])
    return {"authorization_url": data["authorization_url"], "reference": payment["reference"], "amount_minor": amount}


async def verify_and_apply(db, reference: str) -> dict:
    """Source of truth = Paystack verify API. Never trusts the browser redirect."""
    payment = await db.payments.find_one({"reference": reference})
    if not payment:
        raise HTTPException(404, "Payment not found")
    if payment["status"] in ("success", "flagged"):
        return payment
    try:
        data = await paystack.get_client().verify(reference)
    except paystack.PaystackNotConfigured:
        raise HTTPException(503, "Payment gateway not configured")
    except paystack.PaystackError:
        return payment  # unknown right now; stays pending and can be re-verified (webhook/poll)
    st = data.get("status")
    if st == "success":
        if int(data.get("amount", -1)) != payment["amount"] or str(data.get("currency", "")).upper() != payment["currency"]:
            await db.payments.update_one({"_id": payment["_id"]}, {"$set": {"status": "flagged", "failure": "amount/currency mismatch", "gateway_amount": data.get("amount"), "gateway_currency": data.get("currency")}})
            await recompute(db, payment["reservation_id"])
            await notify_staff(db, "attention", f"Payment mismatch {reference}", "Paystack amount/currency differ from the expected values. Not applied.", None, "payments.view", email=True)
            return await db.payments.find_one({"_id": payment["_id"]})
        extra = {"status": "success", "paid_at": utcnow(), "updated_at": utcnow(), "channel": data.get("channel"),
                 "gateway_status": st, "failure": None}
        won = await db.payments.find_one_and_update(
            {"_id": payment["_id"], "status": {"$in": ["pending", "failed", "abandoned"]}},
            {"$set": extra}, return_document=ReturnDocument.AFTER,
        )
        if won is None:  # another worker already settled it (duplicate webhook / poll): idempotent no-op
            return await db.payments.find_one({"_id": payment["_id"]})
        if data.get("id") is not None:
            try:
                await db.payments.update_one({"_id": payment["_id"]}, {"$set": {"paystack_transaction_id": str(data["id"])}})
            except DuplicateKeyError:
                pass
        await _receipt(db, payment["_id"])
        won = await db.payments.find_one({"_id": payment["_id"]})
        await audit(None, "payment.success", "payment", payment["_id"], after={"reference": reference, "amount": payment["amount"]})
        await after_success(db, won)
        return won
    if st == "abandoned" and utcnow() - payment["created_at"] < timedelta(minutes=30):
        # Paystack reports "abandoned" for any checkout not yet completed; the guest may still be paying.
        return await db.payments.find_one({"_id": payment["_id"]})
    if st in ("failed", "abandoned", "reversed"):
        new = "abandoned" if st == "abandoned" else "failed"
        await db.payments.update_one({"_id": payment["_id"], "status": "pending"},
                                     {"$set": {"status": new, "gateway_status": st, "failure": data.get("gateway_response"), "updated_at": utcnow()}})
        await recompute(db, payment["reservation_id"])
    return await db.payments.find_one({"_id": payment["_id"]})


# ---------------- offline ----------------
async def record_offline(db, res: dict, amount: int, method: str, note: str, user: dict) -> dict:
    from .reservations import confirm_reservation

    if res["status"] in ("cancelled", "expired", "no_show"):
        raise HTTPException(409, "Cannot record a payment on a closed reservation")
    if amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    if amount > res["balance"]:
        raise HTTPException(400, "Amount exceeds the outstanding balance")
    now = utcnow()
    p = {"_id": new_id(), "reservation_id": res["_id"], "reservation_reference": res["reference"],
         "reference": f"NLHO{today().year}{secrets.token_hex(6).upper()}", "amount": amount, "currency": res["pricing"]["currency"],
         "method": method, "kind": "offline", "status": "success", "note": note, "paid_at": now, "created_at": now,
         "updated_at": now, "recorded_by": user["_id"], "recorded_by_name": user["name"]}
    await db.payments.insert_one(p)
    await _receipt(db, p["_id"])
    p = await db.payments.find_one({"_id": p["_id"]})
    await audit(user, "payment.record", "payment", p["_id"], after={"reservation": res["reference"], "amount": amount, "method": method})
    await recompute(db, res["_id"])
    fresh = await db.reservations.find_one({"_id": res["_id"]})
    if fresh["status"] == "pending" and fresh["amount_paid"] >= fresh.get("confirm_threshold", fresh["total_amount"]):
        await confirm_reservation(db, res["_id"], user)
    await recompute(db, res["_id"])
    return p


# ---------------- refunds ----------------
async def request_refund(db, res: dict, amount: int, reason: str, user: dict | None, payment_id: str | None = None) -> list[dict]:
    if amount <= 0:
        raise HTTPException(400, "Refund amount must be positive")
    payments = await db.payments.find({"reservation_id": res["_id"], "status": "success"}).to_list(None)
    if payment_id:
        payments = [p for p in payments if p["_id"] == payment_id]
    payments.sort(key=lambda p: p["paid_at"], reverse=True)
    existing = await db.refunds.find({"reservation_id": res["_id"], "status": {"$nin": ["rejected", "failed"]}}).to_list(None)
    remaining = amount
    created = []
    for p in payments:
        used = sum(r["amount"] for r in existing if r["payment_id"] == p["_id"])
        room = p["amount"] - used
        take = min(room, remaining)
        if take <= 0:
            continue
        r = {"_id": new_id(), "reservation_id": res["_id"], "reservation_reference": res["reference"], "payment_id": p["_id"],
             "payment_reference": p["reference"], "amount": take, "currency": p["currency"], "reason": reason,
             "method": "paystack" if p["method"] == "paystack" else "manual", "status": "requested",
             "requested_by": user["_id"] if user else None, "created_at": utcnow(), "updated_at": utcnow()}
        await db.refunds.insert_one(r)
        created.append(r)
        remaining -= take
        if remaining <= 0:
            break
    if remaining > 0:
        for r in created:
            await db.refunds.delete_one({"_id": r["_id"]})
        raise HTTPException(400, "Refund exceeds the amount available to refund")
    await recompute(db, res["_id"])
    for r in created:
        await audit(user, "refund.request", "refund", r["_id"], after={"reservation": res["reference"], "amount": r["amount"], "reason": reason})
    await notify_staff(db, "refund", f"Refund requested – {res['reference']}", reason, f"/admin/refunds", "refunds.view")
    return created


async def process_refund(db, refund: dict, user: dict, note: str = "") -> dict:
    if refund["status"] not in ("requested", "approved"):
        raise HTTPException(409, f"Refund is already {refund['status']}")
    res = await db.reservations.find_one({"_id": refund["reservation_id"]})
    new_status, extra = "processed", {}
    if refund["method"] == "paystack":
        try:
            data = await paystack.get_client().refund(transaction=refund["payment_reference"], amount=refund["amount"],
                                                      currency=refund["currency"], note=refund.get("reason", ""))
        except paystack.PaystackNotConfigured:
            raise HTTPException(503, "Payment gateway not configured")
        except paystack.PaystackError as e:
            raise HTTPException(502, f"Paystack refused the refund: {e}")
        gst = str(data.get("status", "pending")).lower()
        new_status = "processed" if gst == "processed" else "processing"
        extra = {"paystack_refund_id": str(data.get("id", "")) or None, "gateway_status": gst}
    upd = {"status": new_status, "processed_by": user["_id"], "processed_at": utcnow(), "updated_at": utcnow(), "note": note, **extra}
    await db.refunds.update_one({"_id": refund["_id"]}, {"$set": upd})
    await audit(user, "refund.process", "refund", refund["_id"], after={"status": new_status, "amount": refund["amount"]})
    res = await recompute(db, refund["reservation_id"])
    if new_status == "processed":
        await notify_guest(db, "refund_notification", res, f"Refund of {refund['amount'] / 100:,.2f} {refund['currency']} has been processed.")
    else:
        await notify_guest(db, "refund_notification", res, "Your refund has been submitted and is being processed.")
    return await db.refunds.find_one({"_id": refund["_id"]})


async def refund_webhook_update(db, data: dict, status: str) -> None:
    q = {"status": "processing"}
    rid = str(data.get("id", ""))
    refund = None
    if rid:
        refund = await db.refunds.find_one({"paystack_refund_id": rid})
    if not refund and data.get("transaction_reference"):
        refund = await db.refunds.find_one({"payment_reference": data["transaction_reference"], **q})
    if not refund or refund["status"] in ("processed", "failed"):
        return
    await db.refunds.update_one({"_id": refund["_id"]}, {"$set": {"status": status, "updated_at": utcnow()}})
    res = await recompute(db, refund["reservation_id"])
    if status == "processed":
        await notify_guest(db, "refund_notification", res, f"Refund of {refund['amount'] / 100:,.2f} {refund['currency']} has been processed.")
