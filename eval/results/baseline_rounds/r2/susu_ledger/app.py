from decimal import Decimal, ROUND_HALF_UP
import re
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Susu Group Records")

_lock = threading.Lock()
_groups: Dict[int, dict] = {}
_members: Dict[int, dict] = {}
_contributions: List[dict] = []
_collections: List[dict] = []
_ids = {"group": 0, "member": 0, "contribution": 0, "collection": 0}

PHONE_RE = re.compile(r"^\+?[0-9]{9,15}$")
MAX_AMOUNT = Decimal("1000000000")


def _next(kind: str) -> int:
    _ids[kind] += 1
    return _ids[kind]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cedis(pesewas: int) -> float:
    return round(pesewas / 100, 2)


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class MemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=30)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        v = re.sub(r"[\s\-]", "", v.strip())
        if not PHONE_RE.match(v):
            raise ValueError("phone must be 9 to 15 digits, optionally starting with +")
        return v


class ContributionIn(BaseModel):
    member_id: int = Field(ge=1)
    round: int = Field(ge=1, le=100000)
    amount: Decimal

    @field_validator("member_id", "round", mode="before")
    @classmethod
    def _no_bool(cls, v):
        if isinstance(v, bool):
            raise ValueError("must be a whole number")
        return v

    @field_validator("amount", mode="before")
    @classmethod
    def _amount_type(cls, v):
        if isinstance(v, bool) or v is None:
            raise ValueError("amount must be a number")
        return v

    @field_validator("amount")
    @classmethod
    def _amount(cls, v: Decimal) -> Decimal:
        if not v.is_finite():
            raise ValueError("amount must be a real number")
        if v <= 0:
            raise ValueError("amount must be more than zero")
        if v > MAX_AMOUNT:
            raise ValueError("amount is too large")
        if v != v.quantize(Decimal("0.01")):
            raise ValueError("amount can have at most 2 decimal places (pesewas)")
        return v


class CollectIn(BaseModel):
    member_id: int = Field(ge=1)

    @field_validator("member_id", mode="before")
    @classmethod
    def _no_bool(cls, v):
        if isinstance(v, bool):
            raise ValueError("must be a whole number")
        return v


def _get_group(gid: int) -> dict:
    g = _groups.get(gid)
    if g is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return g


def _get_member(gid: int, mid: int) -> dict:
    m = _members.get(mid)
    if m is None or m["group_id"] != gid:
        raise HTTPException(status_code=404, detail="Member not found in this group")
    return m


def _round_collection(gid: int, rnd: int) -> Optional[dict]:
    for c in _collections:
        if c["group_id"] == gid and c["round"] == rnd:
            return c
    return None


def _member_out(m: dict) -> dict:
    return {"id": m["id"], "group_id": m["group_id"], "name": m["name"], "phone": m["phone"], "joined_at": m["joined_at"]}


def _contrib_out(c: dict) -> dict:
    return {"id": c["id"], "group_id": c["group_id"], "member_id": c["member_id"],
            "member_name": _members[c["member_id"]]["name"], "round": c["round"],
            "amount_cedis": _cedis(c["pesewas"]), "paid_at": c["paid_at"]}


def _collect_out(c: dict) -> dict:
    return {"id": c["id"], "group_id": c["group_id"], "round": c["round"], "member_id": c["member_id"],
            "member_name": _members[c["member_id"]]["name"], "pot_cedis": _cedis(c["pesewas"]),
            "collected_at": c["collected_at"]}


@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    with _lock:
        gid = _next("group")
        g = {"id": gid, "name": body.name, "created_at": _now()}
        _groups[gid] = g
        return g


@app.get("/groups")
def list_groups():
    with _lock:
        return list(_groups.values())


@app.get("/groups/{gid}")
def get_group(gid: int):
    with _lock:
        g = _get_group(gid)
        count = sum(1 for m in _members.values() if m["group_id"] == gid)
        return {**g, "member_count": count}


@app.post("/groups/{gid}/members", status_code=201)
def add_member(gid: int, body: MemberIn):
    with _lock:
        _get_group(gid)
        for m in _members.values():
            if m["group_id"] == gid and m["phone"] == body.phone:
                raise HTTPException(status_code=409, detail="A member with this phone number is already in the group")
        mid = _next("member")
        m = {"id": mid, "group_id": gid, "name": body.name, "phone": body.phone, "joined_at": _now()}
        _members[mid] = m
        return _member_out(m)


@app.get("/groups/{gid}/members")
def list_members(gid: int):
    with _lock:
        _get_group(gid)
        return [_member_out(m) for m in _members.values() if m["group_id"] == gid]


@app.get("/groups/{gid}/members/{mid}")
def get_member(gid: int, mid: int):
    with _lock:
        _get_group(gid)
        return _member_out(_get_member(gid, mid))


@app.post("/groups/{gid}/contributions", status_code=201)
def add_contribution(gid: int, body: ContributionIn):
    with _lock:
        _get_group(gid)
        _get_member(gid, body.member_id)
        if _round_collection(gid, body.round) is not None:
            raise HTTPException(status_code=409, detail="This round has already been collected; no more payments can be made into it")
        pesewas = int((body.amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        c = {"id": _next("contribution"), "group_id": gid, "member_id": body.member_id,
             "round": body.round, "pesewas": pesewas, "paid_at": _now()}
        _contributions.append(c)
        return _contrib_out(c)


@app.get("/groups/{gid}/contributions")
def list_contributions(gid: int, round: Optional[int] = None):
    with _lock:
        _get_group(gid)
        return [_contrib_out(c) for c in _contributions
                if c["group_id"] == gid and (round is None or c["round"] == round)]


@app.get("/groups/{gid}/rounds/{rnd}")
def round_summary(gid: int, rnd: int):
    with _lock:
        _get_group(gid)
        cs = [c for c in _contributions if c["group_id"] == gid and c["round"] == rnd]
        col = _round_collection(gid, rnd)
        return {"group_id": gid, "round": rnd,
                "pot_cedis": _cedis(sum(c["pesewas"] for c in cs)),
                "contributions": [_contrib_out(c) for c in cs],
                "collected": col is not None,
                "collection": _collect_out(col) if col else None}


@app.post("/groups/{gid}/rounds/{rnd}/collect", status_code=201)
def collect_round(gid: int, rnd: int, body: CollectIn):
    if rnd < 1:
        raise HTTPException(status_code=422, detail="Round must be 1 or more")
    with _lock:
        _get_group(gid)
        _get_member(gid, body.member_id)
        if _round_collection(gid, rnd) is not None:
            raise HTTPException(status_code=409, detail="This round has already been collected")
        for c in _collections:
            if c["group_id"] == gid and c["member_id"] == body.member_id:
                raise HTTPException(status_code=409, detail=f"This member already collected in round {c['round']}")
        pot = sum(c["pesewas"] for c in _contributions if c["group_id"] == gid and c["round"] == rnd)
        if pot <= 0:
            raise HTTPException(status_code=409, detail="Nobody has paid into this round, so it cannot be collected")
        col = {"id": _next("collection"), "group_id": gid, "round": rnd, "member_id": body.member_id,
               "pesewas": pot, "collected_at": _now()}
        _collections.append(col)
        return _collect_out(col)


@app.get("/groups/{gid}/collections")
def list_collections(gid: int):
    with _lock:
        _get_group(gid)
        return sorted([_collect_out(c) for c in _collections if c["group_id"] == gid], key=lambda x: x["round"])


@app.get("/groups/{gid}/members/{mid}/statement")
def statement(gid: int, mid: int):
    with _lock:
        _get_group(gid)
        m = _get_member(gid, mid)
        paid = [c for c in _contributions if c["group_id"] == gid and c["member_id"] == mid]
        got = [c for c in _collections if c["group_id"] == gid and c["member_id"] == mid]
        total_paid = sum(c["pesewas"] for c in paid)
        total_received = sum(c["pesewas"] for c in got)
        return {"member": _member_out(m),
                "total_paid_cedis": _cedis(total_paid),
                "total_received_cedis": _cedis(total_received),
                "balance_cedis": _cedis(total_received - total_paid),
                "has_collected": len(got) > 0,
                "payments": [_contrib_out(c) for c in paid],
                "collections": [_collect_out(c) for c in got]}
