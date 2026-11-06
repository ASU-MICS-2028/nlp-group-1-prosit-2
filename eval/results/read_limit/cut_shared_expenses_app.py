from decimal import Decimal, InvalidOperation
from typing import List, Optional, Any, Dict
from threading import Lock
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Shared Costs Tracker")

LOCK = Lock()
GROUPS: Dict[int, dict] = {}
COUNTERS = {"group": 0, "expense": 0, "payment": 0}


def next_id(kind: str) -> int:
    COUNTERS[kind] += 1
    return COUNTERS[kind]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_pesewas(value: Any) -> int:
    if value is None or isinstance(value, bool):
        raise HTTPException(422, "Amount is required and must be a number in cedis.")
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise HTTPException(422, "Amount must be a number in cedis, e.g. 12.50.")
    if not d.is_finite():
        raise HTTPException(422, "Amount must be a finite number.")
    if d <= 0:
        raise HTTPException(422, "Amount must be more than zero.")
    p = d * 100
    if p != p.to_integral_value():
        raise HTTPException(422, "Amount cannot have more than 2 decimal places (pesewas).")
    p = int(p)
    if p <= 0:
        raise HTTPException(422, "Amount must be more than zero.")
    return p


def cedis(p: int) -> float:
    return round(p / 100, 2)


def money(p: int) -> dict:
    sign = "-" if p < 0 else ""
    a = abs(p)
    return {"cedis": cedis(p), "pesewas": p, "display": f"{sign}GHS {a // 100}.{a % 100:02d}"}


def clean_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(422, "Names must be non-empty text.")
    return " ".join(name.split())


def get_group(gid: int) -> dict:
    g = GROUPS.get(gid)
    if g is None:
        raise HTTPException(404, f"Group {gid} not found.")
    return g


def find_member(g: dict, name: Any) -> str:
    n = clean_name(name)
    for m in g["members"]:
        if m.lower() == n.lower():
            return m
    raise HTTPException(400, f"'{n}' is not a member of group '{g['name']}'.")


def add_member(g: dict, name: Any) -> str:
    n = clean_name(name)
    for m in g["members"]:
        if m.lower() == n.lower():
            raise HTTPException(409, f"'{n}' is already in the group.")
    g["members"].append(n)
    return n


def split(total: int, k: int) -> List[int]:
    base, rem = divmod(total, k)
    return [base + (1 if i < rem else 0) for i in range(k)]


def balances(g: dict) -> Dict[str, int]:
    b = {m: 0 for m in g["members"]}
    for e in g["expenses"]:
        b[e["paid_by"]] += e["amount_p"]
        for s in e["shares"]:
            b[s["member"]] -= s["pesewas"]
    for p in g["payments"]:
        b[p["from_member"]] += p["amount_p"]
        b[p["to_member"]] -= p["amount_p"]
    assert sum(b.values()) == 0
    return b


def expense_out(e: dict) -> dict:
    return {
        "id": e["id"], "description": e["description"], "paid_by": e["paid_by"],
        "amount": money(e["amount_p"]), "category": e.get("category"),
        "shares": [{"member": s["member"], "share": money(s["pesewas"])} for s in e["shares"]],
        "created_at": e["created_at"],
    }


def payment_out(p: dict) -> dict:
    return {
        "id": p["id"], "from_member": p["from_member"], "to_member": p["to_member"],
        "amount": money(p["amount_p"]), "note": p["note"], "created_at": p["created_at"],
    }


def balances_out(g: dict) -> dict:
    b = balances(g)
    items = []
    for m in g["members"]:
        v = b[m]
        status = "is owed" if v > 0 else ("owes" if v < 0 else "settled")
        items.append({"member": m, "balance": money(v), "status": status})
    return {"group_id": g["id"], "balances": items, "total": money(sum(b.values()))}


def group_out(g: dict) -> dict:
    return {"id": g["id"], "name": g["name"], "members": list(g["members"]), "created_at": g["created_at"]}


class GroupIn(BaseModel):
    name: str
    members: List[str] = []


class MemberIn(BaseModel):
    name: str


class ExpenseIn(BaseModel):
    paid_by: str
    amount: Any = None
    split_between: List[str]
    description: Optional[str] = ""
    category: Optional[str] = None


class PaymentIn(BaseModel):
    from_member: str
    to_member: str
    amount: Any = None
    note: Optional[str] = ""


@app.get("/")
def root():
    return {"message": "Shared costs tracker. See /docs for all endpoints."}


@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    with LOCK:
        name = clean_name(body.name)
        g = {"id": 0, "name": name, "members": [], "expenses": [], "payments": [], "created_at": now()}
        for m in body.members:
            add_member(g, m)
        g["id"] = next_id("group")
        GROUPS[g["id"]] = g
        return group_out(g)


@app.get("/groups")
def list_groups():
    return [group_out(g) for g in GROUPS.values()]


@app.get("/groups/{gid}")
def read_group(gid: int):
    g = get_group(gid)
    out = group_out(g)
    out.update(balances_out(g))
    return out


@app.post("/groups/{gid}/members", status_code=201)
def create_member(gid: int, body: MemberIn):
    with LOCK:
        g = get_group(gid)
        n = add_member(g, body.name)
        return {"group_id": gid, "member": n, "members": list(g["members"])}


@app.get("/groups/{gid}/members")
def list_members(gid: int):
    return balances_out(get_group(gid))["balances"]


@app.get("/groups/{gid}/members/{name}")
def read_member(gid: int, name: str):
    g = get_group(gid)
    m = find_member(g, name)
    v = balances(g)[m]
    return {"group_id": gid, "member": m, "balance": money(v),
            "status": "is owed" if v > 0 else ("owes" if v < 0 else "settled")}


@app.post("/groups/{gid}/expenses", status_code=201)
def create_expense(gid: int, body: ExpenseIn):
    with LOCK:
        g = get_group(gid)
        amount = to_pesewas(body.amount)
        payer = find_member(g, body.paid_by)
        if not body.split_between:
            raise HTTPException(422, "An expense must be shared between at least one member.")
        between = []
        for n in body.split_between:
            m = find_member(g, n)
            if m in between:
                raise HTTPException(422, f"'{m}' is listed more than once in split_between.")
            between.append(m)
        parts = split(amount, len(between))
        assert sum(parts) == amount and max(parts) - min(parts) <= 1
        e = {"id": next_id("expense"), "description": (body.description or "").strip(), "paid_by": payer,
             "amount_p": amount, "category": " ".join(body.category.split()) or None if body.category else None,
             "shares": [{"member": m, "pesewas": p} for m, p in zip(between, parts)],
             "created_at": now()}
        g["expenses"].append(e)
        out = expense_out(e)
        out["balances"] = balances_out(g)["balances"]
        return out


@app.get("/groups/{gid}/expenses")
def list_expenses(gid: int):
    return [expense_out(e) for e in get_group(gid)["expenses"]]


@app.get("/groups/{gid}/expenses/{eid}")
def read_expense(gid: int, eid: int):
    for e in get_group(gid)["expenses"]:
        if e["id"] == eid:
            return expense_out(e)
    raise HTTPException(404, f"Expense {eid} not found in this group.")


@app.post("/groups/{gid}/payments", status_code=201)
def create_payment(gid: int, body: PaymentIn):
    with LOCK:
        g = get_group(gid)
        amount = to_pesewas(body.amount)
        a = find_member(g, body.from_member)
        b = find_member(g, body.to_member)
        if a == b:
            raise HTTPException(422, "Nobody can pay themselves back.")
        p = {"id": next_id("payment"), "from_member": a, "to_member": b, "amount_p": amount,
             "note": (body.note or "").strip(), "created_at": now()}
        g["payments"].append(p)
        out = payment_out(p)
        out["balances"] = balances_out(g)["balances"]
        return out


@app.get("/groups/{gid}/payments")
def list_payments(gid: int):
    return [payment_out(p) for p in get_group(gid)["payments"]]


@app.get("/groups/{gid}/balances")
def group_balances(gid: int):
    return balances_out(get_group(gid))


@app.get("/groups/{gid}/settle-up")
def settle_up(gid: int):
    g = get_group(gid)
    b = balances(g)
    debtors = sorted([[m, -v] for m, v in b.items() if v < 0], key=lambda x: -x[1])
    creditors = sorted([[m, v] for m, v in b.items() if v > 0], key=lambda x: -x[1])
    out = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        amt = min(debtors[i][1], creditors[j][1])
        out.append({"from_member": debtors[i][0], "to_member": creditors[j][0], "amount": money(amt)})
        debtors[i][1] -= amt
        creditors[j][1] -= amt
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return {"group_id": gid, "suggested_payments": out}
