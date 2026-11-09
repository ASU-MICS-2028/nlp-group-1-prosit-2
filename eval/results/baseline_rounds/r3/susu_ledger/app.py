from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional
import re

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Susu Group Records")

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


def _cedis(pesewas: int) -> float:
    return round(pesewas / 100, 2)


# ---------- Input models ----------

class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
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
        v = v.strip()
        cleaned = re.sub(r"[\s\-()]", "", v)
        if not re.fullmatch(r"\+?\d{9,15}", cleaned):
            raise ValueError("phone must be a valid phone number (9 to 15 digits, optional leading +)")
        return cleaned


class ContributionIn(BaseModel):
    member_id: int = Field(gt=0, strict=True)
    round: int = Field(gt=0, strict=True)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2, description="Amount in cedis, more than zero")


class CollectIn(BaseModel):
    member_id: int = Field(gt=0, strict=True)


# ---------- Helpers ----------

def _get_group(group_id: int) -> dict:
    g = _groups.get(group_id)
    if g is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return g


def _get_member(group_id: int, member_id: int) -> dict:
    m = _members.get(member_id)
    if m is None or m["group_id"] != group_id:
        raise HTTPException(status_code=404, detail="Member not found in this group")
    return m


def _member_out(m: dict) -> dict:
    return {"id": m["id"], "group_id": m["group_id"], "name": m["name"], "phone": m["phone"], "joined_at": m["joined_at"]}


def _contribution_out(c: dict) -> dict:
    return {
        "id": c["id"], "group_id": c["group_id"], "member_id": c["member_id"],
        "member_name": _members[c["member_id"]]["name"], "round": c["round"],
        "amount": _cedis(c["pesewas"]), "paid_at": c["paid_at"],
    }


def _collection_out(c: dict) -> dict:
    return {
        "id": c["id"], "group_id": c["group_id"], "round": c["round"],
        "member_id": c["member_id"], "member_name": _members[c["member_id"]]["name"],
        "amount": _cedis(c["pesewas"]), "collected_at": c["collected_at"],
    }


def _round_collection(group_id: int, rnd: int) -> Optional[dict]:
    for c in _collections:
        if c["group_id"] == group_id and c["round"] == rnd:
            return c
    return None


def _round_total(group_id: int, rnd: int) -> int:
    return sum(c["pesewas"] for c in _contributions if c["group_id"] == group_id and c["round"] == rnd)


# ---------- Groups ----------

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
        return [dict(g) for g in _groups.values()]


@app.get("/groups/{group_id}")
def get_group(group_id: int):
    with _lock:
        g = _get_group(group_id)
        members = [m for m in _members.values() if m["group_id"] == group_id]
        return {**g, "member_count": len(members),
                "total_paid_in": _cedis(sum(c["pesewas"] for c in _contributions if c["group_id"] == group_id)),
                "total_paid_out": _cedis(sum(c["pesewas"] for c in _collections if c["group_id"] == group_id))}


# ---------- Members ----------

@app.post("/groups/{group_id}/members", status_code=201)
def add_member(group_id: int, body: MemberIn):
    with _lock:
        _get_group(group_id)
        for m in _members.values():
            if m["group_id"] == group_id and m["phone"] == body.phone:
                raise HTTPException(status_code=409, detail="A member with this phone number is already in the group")
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


@app.get("/groups/{group_id}/members/{member_id}/statement")
def member_statement(group_id: int, member_id: int):
    with _lock:
        _get_group(group_id)
        m = _get_member(group_id, member_id)
        paid = [c for c in _contributions if c["group_id"] == group_id and c["member_id"] == member_id]
        received = [c for c in _collections if c["group_id"] == group_id and c["member_id"] == member_id]
        total_paid = sum(c["pesewas"] for c in paid)
        total_received = sum(c["pesewas"] for c in received)
        return {
            "member": _member_out(m),
            "total_paid_in": _cedis(total_paid),
            "total_received": _cedis(total_received),
            "balance": _cedis(total_received - total_paid),
            "has_collected": len(received) > 0,
            "payments": [_contribution_out(c) for c in paid],
            "collections": [_collection_out(c) for c in received],
        }


# ---------- Contributions ----------

@app.post("/groups/{group_id}/contributions", status_code=201)
def record_contribution(group_id: int, body: ContributionIn):
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Contribution must be more than zero")
    pesewas = int((body.amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if pesewas <= 0:
        raise HTTPException(status_code=400, detail="Contribution must be more than zero")
    with _lock:
        _get_group(group_id)
        _get_member(group_id, body.member_id)
        if _round_collection(group_id, body.round) is not None:
            raise HTTPException(status_code=409, detail=f"Round {body.round} has already been collected; no more payments can be made into it")
        cid = _next("contribution")
        c = {"id": cid, "group_id": group_id, "member_id": body.member_id, "round": body.round,
             "pesewas": pesewas, "paid_at": _now()}
        _contributions.append(c)
        return _contribution_out(c)


@app.get("/groups/{group_id}/contributions")
def list_contributions(group_id: int, round: Optional[int] = None, member_id: Optional[int] = None):
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
            out.append(_contribution_out(c))
        return out


# ---------- Rounds & Collections ----------

@app.get("/groups/{group_id}/rounds/{round_number}")
def get_round(group_id: int, round_number: int):
    if round_number <= 0:
        raise HTTPException(status_code=400, detail="Round number must be 1 or more")
    with _lock:
        _get_group(group_id)
        col = _round_collection(group_id, round_number)
        payments = [c for c in _contributions if c["group_id"] == group_id and c["round"] == round_number]
        return {
            "group_id": group_id, "round": round_number,
            "pot": _cedis(sum(c["pesewas"] for c in payments)),
            "collected": col is not None,
            "collection": _collection_out(col) if col else None,
            "payments": [_contribution_out(c) for c in payments],
        }


@app.get("/groups/{group_id}/rounds")
def list_rounds(group_id: int):
    with _lock:
        _get_group(group_id)
        rounds = sorted({c["round"] for c in _contributions if c["group_id"] == group_id})
        out = []
        for r in rounds:
            col = _round_collection(group_id, r)
            out.append({"round": r, "pot": _cedis(_round_total(group_id, r)), "collected": col is not None,
                        "collector_id": col["member_id"] if col else None,
                        "collector_name": _members[col["member_id"]]["name"] if col else None})
        return out


@app.post("/groups/{group_id}/rounds/{round_number}/collect", status_code=201)
def collect_round(group_id: int, round_number: int, body: CollectIn):
    if round_number <= 0:
        raise HTTPException(status_code=400, detail="Round number must be 1 or more")
    with _lock:
        _get_group(group_id)
        _get_member(group_id, body.member_id)
        if _round_collection(group_id, round_number) is not None:
            raise HTTPException(status_code=409, detail=f"Round {round_number} has already been collected")
        for c in _collections:
            if c["group_id"] == group_id and c["member_id"] == body.member_id:
                raise HTTPException(status_code=409, detail=f"This member already collected in round {c['round']} and cannot collect again")
        total = _round_total(group_id, round_number)
        if total <= 0:
            raise HTTPException(status_code=409, detail=f"Nobody has paid into round {round_number}, so it cannot be collected")
        cid = _next("collection")
        col = {"id": cid, "group_id": group_id, "round": round_number, "member_id": body.member_id,
               "pesewas": total, "collected_at": _now()}
        _collections.append(col)
        return _collection_out(col)


@app.get("/groups/{group_id}/collections")
def list_collections(group_id: int):
    with _lock:
        _get_group(group_id)
        return [_collection_out(c) for c in sorted((c for c in _collections if c["group_id"] == group_id), key=lambda c: c["round"])]
