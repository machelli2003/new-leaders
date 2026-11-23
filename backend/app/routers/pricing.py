from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from ..audit import audit
from ..db import get_db
from ..hotel_settings import get_settings
from ..security import require
from ..services.pricing import nightly_rate
from ..utils import new_id, parse_date, ser, stay_dates, utcnow
from .common import partial

router = APIRouter(tags=["pricing"])


class RuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: Literal["seasonal", "weekend", "holiday", "date"]
    rate_minor: int = Field(ge=1)
    category_id: str | None = None
    room_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    weekdays: list[int] = []
    priority: int = 0
    active: bool = True

    @model_validator(mode="after")
    def check(self):
        for d in (self.start_date, self.end_date):
            if d:
                parse_date(d)
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        if self.type in ("seasonal", "holiday", "date") and not (self.start_date and self.end_date):
            raise ValueError(f"{self.type} rules need a start and end date")
        if any(w < 0 or w > 6 for w in self.weekdays):
            raise ValueError("weekdays must be 0 (Mon) .. 6 (Sun)")
        return self


RulePatch = partial(RuleIn)


@router.get("/pricing/rules")
async def list_rules(user: dict = Depends(require("pricing.manage"))):
    return [ser(r) for r in await get_db().pricing_rules.find({}).sort([("type", 1), ("start_date", 1)]).to_list(None)]


@router.post("/pricing/rules", status_code=201)
async def create_rule(body: RuleIn, user: dict = Depends(require("pricing.manage"))):
    d = {"_id": new_id(), **body.model_dump(), "created_at": utcnow()}
    await get_db().pricing_rules.insert_one(d)
    await audit(user, "price.rule_create", "pricing_rule", d["_id"], after=d)
    return ser(d)


@router.patch("/pricing/rules/{rid}")
async def update_rule(rid: str, body: RulePatch, user: dict = Depends(require("pricing.manage"))):
    db = get_db()
    before = await db.pricing_rules.find_one({"_id": rid})
    if not before:
        raise HTTPException(404, "Rule not found")
    patch = body.model_dump(exclude_unset=True)
    RuleIn(**{k: v for k, v in {**before, **patch}.items() if k in RuleIn.model_fields})  # revalidate merged rule
    await db.pricing_rules.update_one({"_id": rid}, {"$set": patch})
    await audit(user, "price.rule_update", "pricing_rule", rid, before=before, after=patch)
    return ser(await db.pricing_rules.find_one({"_id": rid}))


@router.delete("/pricing/rules/{rid}")
async def delete_rule(rid: str, user: dict = Depends(require("pricing.manage"))):
    r = await get_db().pricing_rules.delete_one({"_id": rid})
    if not r.deleted_count:
        raise HTTPException(404, "Rule not found")
    await audit(user, "price.rule_delete", "pricing_rule", rid)
    return {"ok": True}


@router.get("/pricing/preview")
async def preview(category_id: str, start: str, days: int = 31, user: dict = Depends(require("pricing.manage"))):
    """Nightly rates the engine would charge for a category, with the rule that produced each rate."""
    db = get_db()
    cat = await db.room_categories.find_one({"_id": category_id})
    if not cat:
        raise HTTPException(404, "Category not found")
    from datetime import timedelta

    s = await get_settings(db)
    rules = await db.pricing_rules.find({"active": {"$ne": False}}).to_list(None)
    a = parse_date(start)
    out = []
    for i in range(min(max(days, 1), 120)):
        d = a + timedelta(days=i)
        rate, src = nightly_rate(d, cat, None, rules, s["booking"]["weekend_days"])
        out.append({"date": d.isoformat(), "rate_minor": rate, "source": src})
    return out


# ---------------- promotions / offers ----------------
class PromoIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    description: str = ""
    code: str | None = Field(default=None, max_length=30, pattern=r"^[A-Za-z0-9_-]*$")
    discount_type: Literal["percent", "fixed"] = "percent"
    value: int = Field(default=0, ge=0)
    min_nights: int = Field(default=1, ge=1)
    valid_from: str | None = None
    valid_to: str | None = None
    show_on_website: bool = False
    hide_code: bool = False
    media_id: str | None = None
    status: Literal["draft", "published", "archived"] = "draft"

    @model_validator(mode="after")
    def check(self):
        if self.discount_type == "percent" and self.value > 100:
            raise ValueError("Percent discount cannot exceed 100")
        if self.code and self.value <= 0:
            raise ValueError("A promo code needs a discount value")
        for d in (self.valid_from, self.valid_to):
            if d:
                parse_date(d)
        return self


PromoPatch = partial(PromoIn)


@router.get("/promotions")
async def list_promos(user: dict = Depends(require("promotions.manage"))):
    return [ser(p) for p in await get_db().promotions.find({}).sort([("created_at", -1)]).to_list(None)]


@router.post("/promotions", status_code=201)
async def create_promo(body: PromoIn, user: dict = Depends(require("promotions.manage"))):
    db = get_db()
    d = {"_id": new_id(), **body.model_dump(), "created_at": utcnow()}
    if d["code"]:
        d["code"] = d["code"].upper()
        if await db.promotions.find_one({"code": d["code"]}):
            raise HTTPException(409, "That promo code already exists")
    else:
        d.pop("code")  # sparse unique index: omit when empty
    await db.promotions.insert_one(d)
    await audit(user, "promotion.create", "promotion", d["_id"], after=d)
    return ser(d)


@router.patch("/promotions/{pid}")
async def update_promo(pid: str, body: PromoPatch, user: dict = Depends(require("promotions.manage"))):
    db = get_db()
    before = await db.promotions.find_one({"_id": pid})
    if not before:
        raise HTTPException(404, "Promotion not found")
    patch = body.model_dump(exclude_unset=True)
    if "code" in patch:
        if patch["code"]:
            patch["code"] = patch["code"].upper()
            other = await db.promotions.find_one({"code": patch["code"]})
            if other and other["_id"] != pid:
                raise HTTPException(409, "That promo code already exists")
        else:
            patch.pop("code")
    await db.promotions.update_one({"_id": pid}, {"$set": patch})
    await audit(user, "promotion.update", "promotion", pid, before=before, after=patch)
    return ser(await db.promotions.find_one({"_id": pid}))


@router.delete("/promotions/{pid}")
async def delete_promo(pid: str, user: dict = Depends(require("promotions.manage"))):
    r = await get_db().promotions.delete_one({"_id": pid})
    if not r.deleted_count:
        raise HTTPException(404, "Promotion not found")
    await audit(user, "promotion.delete", "promotion", pid)
    return {"ok": True}
