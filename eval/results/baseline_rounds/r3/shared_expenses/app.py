from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
import threading

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Shared Costs Tracker")

_lock = threading.Lock()
_groups: Dict[int, dict] = {}
_next_id = {"group": 1, "expense": 1, "payment": 1}


# ---------------- helpers ----------------

def to_pesewas(value: Any) -> int:
    if value is None or isinstance(value, bool):
        raise HTTPException(status_code=422, detail="Amount is required and must be a number of cedis.")
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=422, detail="Amount must be a number of cedis.")
    if not d.is_finite():
        raise HTTPException(status_code=422, detail="Amount must be a finite number.")
    if d <= 0:
        raise HTTPException(status_code=422, detail="Amount must be more than zero.")
    p = d * 100
    if p != p.to_integral_value():
        raise HTTPException(status_code=422, detail="Amount cannot have more than two decimal places (pesewas).")
    return int(p)


def cedis(p: int) -> float:
    return float(Decimal(p) / 100)


def money(p: int) -> dict:
    sign = "-" if p < 0 else ""
    a = abs(p)
    return {"cedis": cedis(p), "pesewas": p, "display": f"{sign}GHS {a // 100}.{a % 100:02d}"}


def clean_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=422, detail="Names must be non-empty text.")
    return name.strip()


def get_group(group_id: int) -> dict:
    g = _groups.get(group_id)
    if g is None:
        raise HTTPException(status_code=404, detail="Group not found.")
    return g


def require_member(g: dict, name: Any, role: str) -> str:
    n = clean_name(name)
    if n not in g["members"]:
        raise HTTPException(status_code=400, detail=f"{role} '{n}' is not a member of this group.")
    return n


def split(total: int, k: int) -> List[int]:
    base, rem = divmod(total, k)
    return [base + (1 if i < rem else 0) for i in range(k)]


def balances(g: dict) -> Dict[str, int]:
    b = {m: 0 for m in g["members"]}
    for e in g["expenses"]:
        b[e["paid_by"]] += e["amount"]
        for name, share in e["shares"].items():
            b[name] -= share
    for p in g["payments"]:
        b[p["paid_by"]] += p["amount"]
        b[p["paid_to"]] -= p["amount"]
    return b


def group_out(g: dict) -> dict:
    b = balances(g)
    return {
        "id": g["id"],
        "name": g["name"],
        "members": list(g["members"]),
        "balances": [{"member": m, "balance": money(v)} for m, v in b.items()],
        "balances_total": money(sum(b.values())),
    }


def expense_out(e: dict) -> dict:
    return {
        "id": e["id"],
        "description": e["description"],
        "paid_by": e["paid_by"],
        "amount": money(e["amount"]),
        "shared_between": list(e["shares"].keys()),
        "shares": [{"member": n, "share": money(s)} for n, s in e["shares"].items()],
    }


def payment_out(p: dict) -> dict:
    return {"id": p["id"], "paid_by": p["paid_by"], "paid_to": p["paid_to"], "amount": money(p["amount"]), "note": p["note"]}


# ---------------- models ----------------

class GroupIn(BaseModel):
    name: str
    members: List[str] = []


class MemberIn(BaseModel):
    name: str


class ExpenseIn(BaseModel):
    paid_by: str
    amount: Any
    shared_between: List[str]
    description: Optional[str] = None


class PaymentIn(BaseModel):
    paid_by: str
    paid_to: str
    amount: Any
    note: Optional[str] = None


# ---------------- routes ----------------

@app.get("/")
def root():
    return {"message": "Shared costs tracker. Amounts are in cedis (GHS). See /docs."}


@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    name = clean_name(body.name)
    members: List[str] = []
    for m in body.members:
        n = clean_name(m)
        if n in members:
            raise HTTPException(status_code=409, detail=f"Member '{n}' is listed twice.")
        members.append(n)
    with _lock:
        gid = _next_id["group"]
        _next_id["group"] += 1
        g = {"id": gid, "name": name, "members": members, "expenses": [], "payments": []}
        _groups[gid] = g
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
def add_member(group_id: int, body: MemberIn):
    with _lock:
        g = get_group(group_id)
        n = clean_name(body.name)
        if n in g["members"]:
            raise HTTPException(status_code=409, detail=f"'{n}' is already in this group.")
        g["members"].append(n)
        return group_out(g)


@app.get("/groups/{group_id}/members")
def list_members(group_id: int):
    with _lock:
        g = get_group(group_id)
        b = balances(g)
        return [{"member": m, "balance": money(v)} for m, v in b.items()]


@app.get("/groups/{group_id}/members/{name}")
def read_member(group_id: int, name: str):
    with _lock:
        g = get_group(group_id)
        n = clean_name(name)
        if n not in g["members"]:
            raise HTTPException(status_code=404, detail="Member not found in this group.")
        return {"member": n, "balance": money(balances(g)[n])}


@app.get("/groups/{group_id}/balances")
def group_balances(group_id: int):
    with _lock:
        g = get_group(group_id)
        b = balances(g)
        return {
            "group_id": g["id"],
            "balances": [{"member": m, "balance": money(v)} for m, v in b.items()],
            "total": money(sum(b.values())),
        }


@app.post("/groups/{group_id}/expenses", status_code=201)
def add_expense(group_id: int, body: ExpenseIn):
    with _lock:
        g = get_group(group_id)
        payer = require_member(g, body.paid_by, "Payer")
        amount = to_pesewas(body.amount)
        if not body.shared_between:
            raise HTTPException(status_code=422, detail="The expense must be shared between at least one member.")
        sharers: List[str] = []
        for s in body.shared_between:
            n = require_member(g, s, "Member")
            if n in sharers:
                raise HTTPException(status_code=422, detail=f"'{n}' is listed twice in shared_between.")
            sharers.append(n)
        parts = split(amount, len(sharers))
        eid = _next_id["expense"]
        _next_id["expense"] += 1
        e = {"id": eid, "description": body.description, "paid_by": payer, "amount": amount,
             "shares": dict(zip(sharers, parts))}
        g["expenses"].append(e)
        return expense_out(e)


@app.get("/groups/{group_id}/expenses")
def list_expenses(group_id: int):
    with _lock:
        return [expense_out(e) for e in get_group(group_id)["expenses"]]


@app.post("/groups/{group_id}/payments", status_code=201)
def add_payment(group_id: int, body: PaymentIn):
    with _lock:
        g = get_group(group_id)
        payer = require_member(g, body.paid_by, "Payer")
        payee = require_member(g, body.paid_to, "Recipient")
        if payer == payee:
            raise HTTPException(status_code=400, detail="Nobody can pay themselves back.")
        amount = to_pesewas(body.amount)
        pid = _next_id["payment"]
        _next_id["payment"] += 1
        p = {"id": pid, "paid_by": payer, "paid_to": payee, "amount": amount, "note": body.note}
        g["payments"].append(p)
        return payment_out(p)


@app.get("/groups/{group_id}/payments")
def list_payments(group_id: int):
    with _lock:
        return [payment_out(p) for p in get_group(group_id)["payments"]]
