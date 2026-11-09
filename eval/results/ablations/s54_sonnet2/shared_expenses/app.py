from decimal import Decimal, InvalidOperation
from typing import List, Optional, Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///./app.db", connect_args={"check_same_thread": False})


class Group(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class Member(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(index=True)
    name: str


class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(index=True)
    paid_by: int
    amount: int  # pesewas


class Share(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    expense_id: int = Field(index=True)
    member_id: int
    amount: int  # pesewas


class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(index=True)
    from_member: int
    to_member: int
    amount: int  # pesewas


SQLModel.metadata.create_all(engine)
app = FastAPI()


class GroupIn(BaseModel):
    name: str
    members: List[str]


class ExpenseIn(BaseModel):
    paid_by: Union[int, str]
    amount: Union[int, float, str]
    participants: List[Union[int, str]]


class PaymentIn(BaseModel):
    from_member: Union[int, str]
    to_member: Union[int, str]
    amount: Union[int, float, str]


def to_pesewas(v) -> int:
    try:
        d = Decimal(str(v))
    except InvalidOperation:
        raise HTTPException(422, "Invalid amount")
    if not d.is_finite() or d <= 0:
        raise HTTPException(422, "Amount must be more than zero")
    p = d * 100
    if p != p.to_integral_value():
        raise HTTPException(422, "Amount cannot have fractions of a pesewa")
    return int(p)


def cedis(p: int) -> float:
    return p / 100


def get_group(s: Session, gid: int) -> Group:
    g = s.get(Group, gid)
    if not g:
        raise HTTPException(404, "Group not found")
    return g


def members_of(s: Session, gid: int):
    return s.exec(select(Member).where(Member.group_id == gid).order_by(Member.id)).all()


def resolve(members, ref) -> int:
    for m in members:
        if isinstance(ref, int) and not isinstance(ref, bool) and m.id == ref:
            return m.id
    for m in members:
        if str(ref) == m.name:
            return m.id
    raise HTTPException(422, f"Member {ref!r} is not in the group")


def balances(s: Session, gid: int):
    ms = members_of(s, gid)
    bal = {m.id: 0 for m in ms}
    for e in s.exec(select(Expense).where(Expense.group_id == gid)).all():
        bal[e.paid_by] += e.amount
        for sh in s.exec(select(Share).where(Share.expense_id == e.id)).all():
            bal[sh.member_id] -= sh.amount
    for p in s.exec(select(Payment).where(Payment.group_id == gid)).all():
        bal[p.from_member] += p.amount
        bal[p.to_member] -= p.amount
    return [{"member_id": m.id, "name": m.name, "balance": cedis(bal[m.id])} for m in ms]


@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    names = [n.strip() for n in body.members]
    if not body.name.strip():
        raise HTTPException(422, "Group name required")
    if not names or any(not n for n in names) or len(set(names)) != len(names):
        raise HTTPException(422, "Members must be non-empty, unique names")
    with Session(engine) as s:
        g = Group(name=body.name)
        s.add(g)
        s.commit()
        s.refresh(g)
        for n in names:
            s.add(Member(group_id=g.id, name=n))
        s.commit()
        return {"id": g.id, "name": g.name,
                "members": [{"id": m.id, "name": m.name} for m in members_of(s, g.id)]}


@app.get("/groups/{gid}")
def read_group(gid: int):
    with Session(engine) as s:
        g = get_group(s, gid)
        return {"id": g.id, "name": g.name,
                "members": [{"id": m.id, "name": m.name} for m in members_of(s, gid)],
                "balances": balances(s, gid)}


@app.get("/groups/{gid}/balances")
def read_balances(gid: int):
    with Session(engine) as s:
        get_group(s, gid)
        return balances(s, gid)


@app.post("/groups/{gid}/expenses", status_code=201)
def add_expense(gid: int, body: ExpenseIn):
    with Session(engine) as s:
        get_group(s, gid)
        ms = members_of(s, gid)
        amount = to_pesewas(body.amount)
        payer = resolve(ms, body.paid_by)
        parts = [resolve(ms, r) for r in body.participants]
        if not parts or len(set(parts)) != len(parts):
            raise HTTPException(422, "Participants must be a non-empty list without repeats")
        base, extra = divmod(amount, len(parts))
        e = Expense(group_id=gid, paid_by=payer, amount=amount)
        s.add(e)
        s.commit()
        s.refresh(e)
        shares = {}
        for i, m in enumerate(parts):
            shares[m] = base + (1 if i < extra else 0)
            s.add(Share(expense_id=e.id, member_id=m, amount=shares[m]))
        s.commit()
        return {"id": e.id, "paid_by": payer, "amount": cedis(amount),
                "shares": [{"member_id": m, "amount": cedis(a)} for m, a in shares.items()]}


@app.post("/groups/{gid}/payments", status_code=201)
def add_payment(gid: int, body: PaymentIn):
    with Session(engine) as s:
        get_group(s, gid)
        ms = members_of(s, gid)
        amount = to_pesewas(body.amount)
        a = resolve(ms, body.from_member)
        b = resolve(ms, body.to_member)
        if a == b:
            raise HTTPException(422, "Nobody can pay themselves back")
        p = Payment(group_id=gid, from_member=a, to_member=b, amount=amount)
        s.add(p)
        s.commit()
        s.refresh(p)
        return {"id": p.id, "from_member": a, "to_member": b, "amount": cedis(amount)}
