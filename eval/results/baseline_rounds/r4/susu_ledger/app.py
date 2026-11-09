from decimal import Decimal
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional
import re

from fastapi import FastAPI, HTTPException, Path, Query
from pydantic import BaseModel, Field, StrictInt, field_validator

app = FastAPI(title="Susu Group Records", description="Keep susu group records: members, contributions, collections and statements. Amounts are in Ghana cedis (GHS).")

_lock = Lock()
_groups: Dict[int, dict] = {}
_members: Dict[int, dict] = {}
_contributions: List[dict] = []
_collections: List[dict] = []
_ids = {"group": 0, "member": 0, "contribution": 0, "collection": 0}


def _next(kind: str) -> int:
    _ids[kind] += 1
    return _ids[kind]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _money(d: Decimal) -> float:
    return float(d.quantize(Decimal("0.01")))


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
        v = v.strip()
        if not re.fullmatch(r"\+?[0-9][0-9 \-]{5,25}", v):
            raise ValueError("phone must be a valid phone number (digits, optional leading +)")
        return v


class ContributionIn(BaseModel):
    member_id: StrictInt
    round: StrictInt = Field(..., ge=1)
    amount: Decimal = Field(..., gt=0, max_digits=14, decimal_places=2, description="Amount in cedis, more than zero, at most 2 decimal places")


class CollectIn(BaseModel):
    member_id: StrictInt


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
    return {"id": c["id"], "group_id": c["group_id"], "member_id": c["member_id"], "member_name": _members[c["member_id"]]["name"], "round": c["round"], "amount": _money(c["amount"]), "paid_at": c["paid_at"]}


def _coll_out(c: dict) -> dict:
    return {"id": c["id"], "group_id": c["group_id"], "round": c["round"], "member_id": c["member_id"], "member_name": _members[c["member_id"]]["name"], "amount": _money(c["amount"]), "collected_at": c["collected_at"]}


def _round_collection(gid: int, rnd: int) -> Optional[dict]:
    for c in _collections:
        if c["group_id"] == gid and c["round"] == rnd:
            return c
    return None


def _pot(gid: int, rnd: int) -> Decimal:
    return sum((c["amount"] for c in _contributions if c["group_id"] == gid and c["round"] == rnd), Decimal("0"))


@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    with _lock:
        gid = _next("group")
        g = {"id": gid, "name": body.name, "created_at": _now()}
        _groups[gid] = g
        return dict(g)


@app.get("/groups")
def list_groups():
    with _lock:
        return [dict(g) for g in _groups.values()]


@app.get("/groups/{group_id}")
def get_group(group_id: int):
    with _lock:
        g = _get_group(group_id)
        n = sum(1 for m in _members.values() if m["group_id"] == group_id)
        return {**g, "member_count": n}


@app.post("/groups/{group_id}/members", status_code=201)
def add_member(group_id: int, body: MemberIn):
    with _lock:
        _get_group(group_id)
        norm = re.sub(r"[ \-]", "", body.phone)
        for m in _members.values():
            if m["group_id"] == group_id and re.sub(r"[ \-]", "", m["phone"]) == norm:
                raise HTTPException(409, "A member with this phone number is already in the group")
        mid = _next("member")
        m = {"id": mid, "group_id": group_id, "name": body.name, "phone": body.phone, "joined_at": _now()}
        _members[mid] = m
        return _member_out(m)


@app.get("/groups/{group_id}/members")
def list_members(group_id: int):
    with _lock:
        _get_group(group_id)
        return [_member_out(m) for m in _members.values() if m["group_id"] == group_id]


@app.get("/groups/{group_id}/members/{member_id}")
def get_member(group_id: int, member_id: int):
    with _lock:
        _get_group(group_id)
        return _member_out(_get_member(group_id, member_id))


@app.post("/groups/{group_id}/contributions", status_code=201)
def record_contribution(group_id: int, body: ContributionIn):
    with _lock:
        _get_group(group_id)
        _get_member(group_id, body.member_id)
        if body.amount <= 0:
            raise HTTPException(422, "Contribution must be more than zero")
        if _round_collection(group_id, body.round) is not None:
            raise HTTPException(409, f"Round {body.round} has already been collected; no more payments can be made into it")
        cid = _next("contribution")
        c = {"id": cid, "group_id": group_id, "member_id": body.member_id, "round": body.round, "amount": body.amount, "paid_at": _now()}
        _contributions.append(c)
        return _contrib_out(c)


@app.get("/groups/{group_id}/contributions")
def list_contributions(group_id: int, round: Optional[int] = Query(None, ge=1), member_id: Optional[int] = None):
    with _lock:
        _get_group(group_id)
        out = []
        for c in _contributions:
            if c["group_id"] != group_id:
                continue
            if round is not None and c["round"] != round:
                continue
            if member_id is not None and c["member_id"] != member_id:
                continue
            out.append(_contrib_out(c))
        return out


@app.get("/groups/{group_id}/rounds/{round_no}")
def get_round(group_id: int, round_no: int = Path(..., ge=1)):
    with _lock:
        _get_group(group_id)
        coll = _round_collection(group_id, round_no)
        return {
            "group_id": group_id,
            "round": round_no,
            "pot": _money(_pot(group_id, round_no)),
            "contributions": [_contrib_out(c) for c in _contributions if c["group_id"] == group_id and c["round"] == round_no],
            "collected": coll is not None,
            "collection": _coll_out(coll) if coll else None,
        }


@app.post("/groups/{group_id}/rounds/{round_no}/collect", status_code=201)
def collect_round(group_id: int, body: CollectIn, round_no: int = Path(..., ge=1)):
    with _lock:
        _get_group(group_id)
        _get_member(group_id, body.member_id)
        if _round_collection(group_id, round_no) is not None:
            raise HTTPException(409, f"Round {round_no} has already been collected")
        for c in _collections:
            if c["group_id"] == group_id and c["member_id"] == body.member_id:
                raise HTTPException(409, f"This member already collected in round {c['round']} and cannot collect again")
        pot = _pot(group_id, round_no)
        if pot <= 0:
            raise HTTPException(409, f"Nobody has paid into round {round_no}, so it cannot be collected")
        cid = _next("collection")
        c = {"id": cid, "group_id": group_id, "round": round_no, "member_id": body.member_id, "amount": pot, "collected_at": _now()}
        _collections.append(c)
        return _coll_out(c)


@app.get("/groups/{group_id}/collections")
def list_collections(group_id: int):
    with _lock:
        _get_group(group_id)
        return sorted((_coll_out(c) for c in _collections if c["group_id"] == group_id), key=lambda x: (x["round"], x["id"]))


@app.get("/groups/{group_id}/members/{member_id}/statement")
def member_statement(group_id: int, member_id: int):
    with _lock:
        _get_group(group_id)
        m = _get_member(group_id, member_id)
        paid = [c for c in _contributions if c["group_id"] == group_id and c["member_id"] == member_id]
        got = [c for c in _collections if c["group_id"] == group_id and c["member_id"] == member_id]
        total_paid = sum((c["amount"] for c in paid), Decimal("0"))
        total_received = sum((c["amount"] for c in got), Decimal("0"))
        return {
            "member": _member_out(m),
            "currency": "GHS",
            "total_paid": _money(total_paid),
            "total_received": _money(total_received),
            "balance": _money(total_received - total_paid),
            "has_collected": bool(got),
            "contributions": [_contrib_out(c) for c in paid],
            "collections": [_coll_out(c) for c in got],
        }
