from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Susu Group Records")

_lock = Lock()
_groups: Dict[int, dict] = {}
_members: Dict[int, dict] = {}
_contributions: List[dict] = []
_collections: List[dict] = []
_ids = {"group": 0, "member": 0, "contribution": 0, "collection": 0}

MAX_AMOUNT = Decimal("100000000")


def _next(kind: str) -> int:
    _ids[kind] += 1
    return _ids[kind]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cedis(pesewas: int) -> float:
    return float(Decimal(pesewas) / Decimal(100))


class GroupIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class MemberIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=1, max_length=30)

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
        v = v.strip().replace(" ", "").replace("-", "")
        digits = v[1:] if v.startswith("+") else v
        if not digits.isdigit() or not (7 <= len(digits) <= 15):
            raise ValueError("phone must be a valid phone number (digits, optional leading +)")
        return v


class ContributionIn(BaseModel):
    member_id: int
    round: int = Field(..., ge=1)
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def _amount(cls, v: Decimal) -> Decimal:
        try:
            if not v.is_finite():
                raise ValueError("amount must be a real number")
        except InvalidOperation:
            raise ValueError("amount must be a real number")
        if v <= 0:
            raise ValueError("amount must be more than zero")
        if v > MAX_AMOUNT:
            raise ValueError("amount is too large")
        if v != v.quantize(Decimal("0.01")):
            raise ValueError("amount can have at most 2 decimal places (pesewas)")
        return v


class CollectIn(BaseModel):
    member_id: int


def _get_group(gid: int) -> dict:
    g = _groups.get(gid)
    if g is None:
        raise HTTPException(404, "Group not found")
    return g


def _get_member(gid: int, mid: int) -> dict:
    m = _members.get(mid)
    if m is None or m["group_id"] != gid:
        raise HTTPException(404, "Member not found in this group")
    return m


def _member_out(m: dict) -> dict:
    return {"id": m["id"], "group_id": m["group_id"], "name": m["name"], "phone": m["phone"], "joined_at": m["joined_at"]}


def _contrib_out(c: dict) -> dict:
    return {"id": c["id"], "group_id": c["group_id"], "member_id": c["member_id"],
            "member_name": _members[c["member_id"]]["name"], "round": c["round"],
            "amount": _cedis(c["pesewas"]), "paid_at": c["paid_at"]}


def _coll_out(c: dict) -> dict:
    return {"id": c["id"], "group_id": c["group_id"], "round": c["round"], "member_id": c["member_id"],
            "member_name": _members[c["member_id"]]["name"], "amount": _cedis(c["pesewas"]),
            "collected_at": c["collected_at"]}


def _round_collection(gid: int, rnd: int) -> Optional[dict]:
    for c in _collections:
        if c["group_id"] == gid and c["round"] == rnd:
            return c
    return None


@app.get("/")
def home():
    return {"message": "Susu group records. See /docs for all actions."}


@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    with _lock:
        gid = _next("group")
        g = {"id": gid, "name": body.name, "created_at": _now()}
        _groups[gid] = g
        return g


@app.get("/groups")
def list_groups():
    return list(_groups.values())


@app.get("/groups/{gid}")
def get_group(gid: int):
    with _lock:
        g = _get_group(gid)
        members = [m for m in _members.values() if m["group_id"] == gid]
        return {**g, "member_count": len(members),
                "collections_made": sum(1 for c in _collections if c["group_id"] == gid)}


@app.post("/groups/{gid}/members", status_code=201)
def add_member(gid: int, body: MemberIn):
    with _lock:
        _get_group(gid)
        for m in _members.values():
            if m["group_id"] == gid and m["phone"] == body.phone:
                raise HTTPException(409, "A member with this phone number is already in the group")
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
            raise HTTPException(409, f"Round {body.round} has already been collected; no more payments allowed")
        cid = _next("contribution")
        c = {"id": cid, "group_id": gid, "member_id": body.member_id, "round": body.round,
             "pesewas": int(body.amount * 100), "paid_at": _now()}
        _contributions.append(c)
        return _contrib_out(c)


@app.get("/groups/{gid}/contributions")
def list_contributions(gid: int, round: Optional[int] = None):
    with _lock:
        _get_group(gid)
        return [_contrib_out(c) for c in _contributions
                if c["group_id"] == gid and (round is None or c["round"] == round)]


@app.get("/groups/{gid}/rounds/{rnd}")
def round_info(gid: int, rnd: int):
    with _lock:
        _get_group(gid)
        cs = [c for c in _contributions if c["group_id"] == gid and c["round"] == rnd]
        coll = _round_collection(gid, rnd)
        return {"round": rnd, "pot": _cedis(sum(c["pesewas"] for c in cs)),
                "contributions": [_contrib_out(c) for c in cs],
                "collected": coll is not None,
                "collection": _coll_out(coll) if coll else None}


@app.post("/groups/{gid}/rounds/{rnd}/collect", status_code=201)
def collect(gid: int, rnd: int, body: CollectIn):
    with _lock:
        _get_group(gid)
        if rnd < 1:
            raise HTTPException(422, "Round must be 1 or more")
        _get_member(gid, body.member_id)
        if _round_collection(gid, rnd) is not None:
            raise HTTPException(409, f"Round {rnd} has already been collected")
        for c in _collections:
            if c["group_id"] == gid and c["member_id"] == body.member_id:
                raise HTTPException(409, f"This member already collected in round {c['round']}")
        pot = sum(c["pesewas"] for c in _contributions if c["group_id"] == gid and c["round"] == rnd)
        if pot <= 0:
            raise HTTPException(409, f"Nobody has paid into round {rnd}; it cannot be collected")
        cid = _next("collection")
        coll = {"id": cid, "group_id": gid, "round": rnd, "member_id": body.member_id,
                "pesewas": pot, "collected_at": _now()}
        _collections.append(coll)
        return _coll_out(coll)


@app.get("/groups/{gid}/collections")
def list_collections(gid: int):
    with _lock:
        _get_group(gid)
        return sorted([_coll_out(c) for c in _collections if c["group_id"] == gid], key=lambda x: x["round"])


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
                "total_paid": _cedis(total_paid),
                "total_received": _cedis(total_received),
                "balance": _cedis(total_received - total_paid),
                "payments": [_contrib_out(c) for c in paid],
                "collections": [_coll_out(c) for c in got]}
