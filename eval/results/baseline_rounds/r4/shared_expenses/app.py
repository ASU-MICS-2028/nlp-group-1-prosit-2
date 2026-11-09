from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Shared Costs Tracker")

_lock = Lock()
_groups: Dict[int, dict] = {}
_next_group_id = 1


# ---------- Models ----------

class GroupCreate(BaseModel):
    name: str
    members: List[str] = []


class MemberCreate(BaseModel):
    name: str


class ExpenseCreate(BaseModel):
    paid_by: str
    amount: Union[Decimal, str, float, int]
    split_between: List[str]
    description: Optional[str] = ""


class PaymentCreate(BaseModel):
    from_member: str
    to_member: str
    amount: Union[Decimal, str, float, int]
    note: Optional[str] = ""


# ---------- Helpers ----------

def to_pesewas(amount) -> int:
    try:
        d = Decimal(str(amount).strip())
    except (InvalidOperation, ValueError):
        raise HTTPException(422, "Amount must be a number in cedis")
    if not d.is_finite():
        raise HTTPException(422, "Amount must be a finite number")
    if d <= 0:
        raise HTTPException(422, "Amount must be more than zero")
    q = d * 100
    if q != q.to_integral_value():
        raise HTTPException(422, "Amount can have at most 2 decimal places (pesewas)")
    p = int(q)
    if p <= 0:
        raise HTTPException(422, "Amount must be more than zero")
    return p


def cedis(p: int) -> float:
    return round(p / 100, 2)


def clean_name(name: str) -> str:
    if not isinstance(name, str):
        raise HTTPException(422, "Name must be text")
    n = name.strip()
    if not n:
        raise HTTPException(422, "Name must not be empty")
    return n


def get_group(group_id: int) -> dict:
    g = _groups.get(group_id)
    if g is None:
        raise HTTPException(404, "Group not found")
    return g


def require_member(g: dict, name: str) -> str:
    n = clean_name(name)
    if n not in g["members"]:
        raise HTTPException(400, f"'{n}' is not a member of this group")
    return n


def compute_balances(g: dict) -> Dict[str, int]:
    bal = {m: 0 for m in g["members"]}
    for e in g["expenses"]:
        bal[e["paid_by"]] += e["amount_pesewas"]
        for m, s in e["shares_pesewas"].items():
            bal[m] -= s
    for p in g["payments"]:
        bal[p["from_member"]] += p["amount_pesewas"]
        bal[p["to_member"]] -= p["amount_pesewas"]
    return bal


def expense_out(e: dict) -> dict:
    return {
        "id": e["id"],
        "description": e["description"],
        "paid_by": e["paid_by"],
        "amount": cedis(e["amount_pesewas"]),
        "amount_pesewas": e["amount_pesewas"],
        "split_between": list(e["shares_pesewas"].keys()),
        "shares": [
            {"member": m, "amount": cedis(s), "amount_pesewas": s}
            for m, s in e["shares_pesewas"].items()
        ],
    }


def payment_out(p: dict) -> dict:
    return {
        "id": p["id"],
        "from_member": p["from_member"],
        "to_member": p["to_member"],
        "amount": cedis(p["amount_pesewas"]),
        "amount_pesewas": p["amount_pesewas"],
        "note": p["note"],
    }


def group_out(g: dict) -> dict:
    return {"id": g["id"], "name": g["name"], "members": list(g["members"])}


def balances_out(g: dict) -> dict:
    bal = compute_balances(g)
    total = sum(bal.values())
    return {
        "group_id": g["id"],
        "balances": [
            {"member": m, "balance": cedis(v), "balance_pesewas": v,
             "status": "is owed" if v > 0 else ("owes" if v < 0 else "settled")}
            for m, v in bal.items()
        ],
        "total": cedis(total),
        "total_pesewas": total,
    }


# ---------- Endpoints ----------

@app.get("/")
def root():
    return {"message": "Shared costs tracker. Amounts are in cedis (GHS)."}


@app.post("/groups", status_code=201)
def create_group(body: GroupCreate):
    global _next_group_id
    name = clean_name(body.name)
    members: List[str] = []
    for m in body.members:
        n = clean_name(m)
        if n in members:
            raise HTTPException(409, f"Member '{n}' listed more than once")
        members.append(n)
    with _lock:
        gid = _next_group_id
        _next_group_id += 1
        g = {"id": gid, "name": name, "members": members, "expenses": [],
             "payments": [], "next_expense_id": 1, "next_payment_id": 1}
        _groups[gid] = g
        return group_out(g)


@app.get("/groups")
def list_groups():
    with _lock:
        return [group_out(g) for g in _groups.values()]


@app.get("/groups/{group_id}")
def read_group(group_id: int):
    with _lock:
        g = get_group(group_id)
        out = group_out(g)
        out.update(balances_out(g))
        return out


@app.post("/groups/{group_id}/members", status_code=201)
def add_member(group_id: int, body: MemberCreate):
    with _lock:
        g = get_group(group_id)
        n = clean_name(body.name)
        if n in g["members"]:
            raise HTTPException(409, f"'{n}' is already a member of this group")
        g["members"].append(n)
        return group_out(g)


@app.get("/groups/{group_id}/members")
def list_members(group_id: int):
    with _lock:
        return get_group(group_id)["members"]


@app.post("/groups/{group_id}/expenses", status_code=201)
def add_expense(group_id: int, body: ExpenseCreate):
    with _lock:
        g = get_group(group_id)
        payer = require_member(g, body.paid_by)
        total = to_pesewas(body.amount)
        if not body.split_between:
            raise HTTPException(422, "Expense must be shared between at least one member")
        parts: List[str] = []
        for m in body.split_between:
            n = require_member(g, m)
            if n in parts:
                raise HTTPException(422, f"'{n}' listed more than once in split_between")
            parts.append(n)
        k = len(parts)
        base, rem = divmod(total, k)
        shares = {}
        for i, m in enumerate(parts):
            shares[m] = base + (1 if i < rem else 0)
        assert sum(shares.values()) == total
        e = {"id": g["next_expense_id"], "description": body.description or "",
             "paid_by": payer, "amount_pesewas": total, "shares_pesewas": shares}
        g["next_expense_id"] += 1
        g["expenses"].append(e)
        return expense_out(e)


@app.get("/groups/{group_id}/expenses")
def list_expenses(group_id: int):
    with _lock:
        return [expense_out(e) for e in get_group(group_id)["expenses"]]


@app.post("/groups/{group_id}/payments", status_code=201)
def add_payment(group_id: int, body: PaymentCreate):
    with _lock:
        g = get_group(group_id)
        frm = require_member(g, body.from_member)
        to = require_member(g, body.to_member)
        if frm == to:
            raise HTTPException(422, "A member cannot pay themselves back")
        amt = to_pesewas(body.amount)
        p = {"id": g["next_payment_id"], "from_member": frm, "to_member": to,
             "amount_pesewas": amt, "note": body.note or ""}
        g["next_payment_id"] += 1
        g["payments"].append(p)
        return payment_out(p)


@app.get("/groups/{group_id}/payments")
def list_payments(group_id: int):
    with _lock:
        return [payment_out(p) for p in get_group(group_id)["payments"]]


@app.get("/groups/{group_id}/balances")
def get_balances(group_id: int):
    with _lock:
        return balances_out(get_group(group_id))


@app.get("/groups/{group_id}/settlements")
def suggested_settlements(group_id: int):
    """Suggests who should pay whom to settle all balances."""
    with _lock:
        bal = compute_balances(get_group(group_id))
    debtors = sorted([[m, -v] for m, v in bal.items() if v < 0], key=lambda x: -x[1])
    creditors = sorted([[m, v] for m, v in bal.items() if v > 0], key=lambda x: -x[1])
    out = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        amt = min(debtors[i][1], creditors[j][1])
        out.append({"from_member": debtors[i][0], "to_member": creditors[j][0],
                    "amount": cedis(amt), "amount_pesewas": amt})
        debtors[i][1] -= amt
        creditors[j][1] -= amt
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return out
