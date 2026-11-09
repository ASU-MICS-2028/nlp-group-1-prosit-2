from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Shared Costs Tracker", description="Track who owes whom in groups. Amounts are in cedis (GHS), stored exactly in pesewas.")

_lock = Lock()
_groups: Dict[int, Dict[str, Any]] = {}
_next_group_id = 1
MAX_PESEWAS = 10**13


class GroupCreate(BaseModel):
    name: str
    members: List[str] = []


class MemberCreate(BaseModel):
    name: str


class ExpenseCreate(BaseModel):
    paid_by: str
    amount: Any
    shared_between: List[str]
    description: Optional[str] = ""


class PaymentCreate(BaseModel):
    from_member: str
    to_member: str
    amount: Any
    note: Optional[str] = ""


def fmt(p: int) -> str:
    sign = "-" if p < 0 else ""
    p = abs(p)
    return f"{sign}{p // 100}.{p % 100:02d}"


def money(p: int) -> Dict[str, Any]:
    return {"cedis": fmt(p), "pesewas": p}


def to_pesewas(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        raise HTTPException(400, "Amount must be a number in cedis, e.g. 25.50")
    if isinstance(value, float):
        value = repr(value)
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise HTTPException(400, "Amount must be a number in cedis, e.g. 25.50")
    if not d.is_finite():
        raise HTTPException(400, "Amount must be a finite number")
    p = d * 100
    if p != p.to_integral_value():
        raise HTTPException(400, "Amount cannot have more than 2 decimal places (smallest unit is one pesewa)")
    p = int(p)
    if p <= 0:
        raise HTTPException(400, "Amount must be more than zero")
    if p > MAX_PESEWAS:
        raise HTTPException(400, "Amount is too large")
    return p


def clean_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(400, "Member name must not be empty")
    n = " ".join(name.split())
    if len(n) > 100:
        raise HTTPException(400, "Member name is too long")
    return n


def get_group(gid: int) -> Dict[str, Any]:
    g = _groups.get(gid)
    if g is None:
        raise HTTPException(404, "Group not found")
    return g


def find_member(g: Dict[str, Any], name: str) -> str:
    if not isinstance(name, str):
        raise HTTPException(400, "Member name must be text")
    key = " ".join(name.split()).lower()
    m = g["members"].get(key)
    if m is None:
        raise HTTPException(400, f"'{name}' is not a member of this group")
    return m


def add_member(g: Dict[str, Any], name: str) -> str:
    n = clean_name(name)
    key = n.lower()
    if key in g["members"]:
        raise HTTPException(409, f"'{n}' is already a member of this group")
    g["members"][key] = n
    g["balances"][n] = 0
    return n


def group_out(g: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": g["id"], "name": g["name"], "members": list(g["members"].values())}


def balances_out(g: Dict[str, Any]) -> Dict[str, Any]:
    items = []
    for name in g["members"].values():
        b = g["balances"][name]
        status = "is owed" if b > 0 else ("owes" if b < 0 else "settled")
        items.append({"member": name, "balance": fmt(b), "balance_pesewas": b, "status": status})
    total = sum(g["balances"].values())
    return {"group_id": g["id"], "balances": items, "total": fmt(total), "total_pesewas": total}


@app.post("/groups", status_code=201)
def create_group(body: GroupCreate):
    global _next_group_id
    if not body.name or not body.name.strip():
        raise HTTPException(400, "Group name must not be empty")
    with _lock:
        g = {"id": _next_group_id, "name": body.name.strip(), "members": {}, "balances": {}, "expenses": [], "payments": [], "next_id": 1}
        seen = set()
        for m in body.members:
            n = clean_name(m)
            if n.lower() in seen:
                raise HTTPException(409, f"'{n}' is listed more than once")
            seen.add(n.lower())
        for m in body.members:
            add_member(g, m)
        _groups[g["id"]] = g
        _next_group_id += 1
        return group_out(g)


@app.get("/groups")
def list_groups():
    with _lock:
        return [group_out(g) for g in _groups.values()]


@app.get("/groups/{group_id}")
def read_group(group_id: int):
    with _lock:
        return group_out(get_group(group_id))


@app.post("/groups/{group_id}/members", status_code=201)
def create_member(group_id: int, body: MemberCreate):
    with _lock:
        g = get_group(group_id)
        add_member(g, body.name)
        return group_out(g)


@app.get("/groups/{group_id}/members")
def list_members(group_id: int):
    with _lock:
        return list(get_group(group_id)["members"].values())


@app.post("/groups/{group_id}/expenses", status_code=201)
def create_expense(group_id: int, body: ExpenseCreate):
    with _lock:
        g = get_group(group_id)
        amount = to_pesewas(body.amount)
        payer = find_member(g, body.paid_by)
        if not body.shared_between:
            raise HTTPException(400, "An expense must be shared between at least one member")
        sharers: List[str] = []
        for n in body.shared_between:
            m = find_member(g, n)
            if m in sharers:
                raise HTTPException(400, f"'{m}' is listed more than once in shared_between")
            sharers.append(m)
        k = len(sharers)
        base, rem = divmod(amount, k)
        shares = []
        for i, m in enumerate(sharers):
            s = base + (1 if i < rem else 0)
            shares.append((m, s))
        assert sum(s for _, s in shares) == amount
        g["balances"][payer] += amount
        for m, s in shares:
            g["balances"][m] -= s
        e = {"id": g["next_id"], "type": "expense", "description": body.description or "", "paid_by": payer,
             "amount": fmt(amount), "amount_pesewas": amount,
             "shares": [{"member": m, "share": fmt(s), "share_pesewas": s} for m, s in shares]}
        g["next_id"] += 1
        g["expenses"].append(e)
        return e


@app.get("/groups/{group_id}/expenses")
def list_expenses(group_id: int):
    with _lock:
        return get_group(group_id)["expenses"]


@app.post("/groups/{group_id}/payments", status_code=201)
def create_payment(group_id: int, body: PaymentCreate):
    with _lock:
        g = get_group(group_id)
        amount = to_pesewas(body.amount)
        frm = find_member(g, body.from_member)
        to = find_member(g, body.to_member)
        if frm == to:
            raise HTTPException(400, "A member cannot pay themselves back")
        g["balances"][frm] += amount
        g["balances"][to] -= amount
        p = {"id": g["next_id"], "type": "payment", "from_member": frm, "to_member": to,
             "amount": fmt(amount), "amount_pesewas": amount, "note": body.note or ""}
        g["next_id"] += 1
        g["payments"].append(p)
        return p


@app.get("/groups/{group_id}/payments")
def list_payments(group_id: int):
    with _lock:
        return get_group(group_id)["payments"]


@app.get("/groups/{group_id}/balances")
def get_balances(group_id: int):
    with _lock:
        return balances_out(get_group(group_id))


@app.get("/groups/{group_id}/balances/{member}")
def get_member_balance(group_id: int, member: str):
    with _lock:
        g = get_group(group_id)
        key = " ".join(member.split()).lower()
        m = g["members"].get(key)
        if m is None:
            raise HTTPException(404, "Member not found in this group")
        b = g["balances"][m]
        return {"member": m, "balance": fmt(b), "balance_pesewas": b}
