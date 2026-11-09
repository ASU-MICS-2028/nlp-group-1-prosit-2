from decimal import Decimal
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///app.db", connect_args={"check_same_thread": False})


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
    description: Optional[str] = None


class ExpenseShare(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    expense_id: int = Field(index=True)
    member_id: int
    share: int  # pesewas


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
    members: List[str] = []


class MemberIn(BaseModel):
    name: str


class ExpenseIn(BaseModel):
    paid_by: int
    amount: Decimal
    shared_between: List[int]
    description: Optional[str] = None


class PaymentIn(BaseModel):
    from_member: int
    to_member: int
    amount: Decimal


def pesewas(x: Decimal) -> int:
    if not x.is_finite() or x <= 0:
        raise HTTPException(422, "amount must be more than zero")
    p = x * 100
    if p != p.to_integral_value():
        raise HTTPException(422, "amount cannot have fractions of a pesewa")
    return int(p)


def cedis(p: int) -> float:
    return p / 100


def clean_name(n: str) -> str:
    n = n.strip()
    if not n:
        raise HTTPException(422, "name must not be empty")
    return n


def get_group(s: Session, gid: int) -> Group:
    g = s.get(Group, gid)
    if not g:
        raise HTTPException(404, "group not found")
    return g


def member_ids(s: Session, gid: int):
    return {m.id for m in s.exec(select(Member).where(Member.group_id == gid))}


def add_member(s: Session, gid: int, name: str) -> Member:
    name = clean_name(name)
    for m in s.exec(select(Member).where(Member.group_id == gid)):
        if m.name == name:
            raise HTTPException(409, "member name already in group")
    m = Member(group_id=gid, name=name)
    s.add(m)
    s.commit()
    s.refresh(m)
    return m


def group_view(s: Session, g: Group):
    ms = s.exec(select(Member).where(Member.group_id == g.id).order_by(Member.id)).all()
    return {"id": g.id, "name": g.name,
            "members": [{"id": m.id, "name": m.name} for m in ms]}


@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    name = clean_name(body.name)
    names = [clean_name(n) for n in body.members]
    if len(set(names)) != len(names):
        raise HTTPException(409, "duplicate member names")
    with Session(engine) as s:
        g = Group(name=name)
        s.add(g)
        s.commit()
        s.refresh(g)
        for n in names:
            add_member(s, g.id, n)
        return group_view(s, g)


@app.get("/groups/{gid}")
def read_group(gid: int):
    with Session(engine) as s:
        return group_view(s, get_group(s, gid))


@app.post("/groups/{gid}/members", status_code=201)
def create_member(gid: int, body: MemberIn):
    with Session(engine) as s:
        get_group(s, gid)
        m = add_member(s, gid, body.name)
        return {"id": m.id, "name": m.name}


@app.post("/groups/{gid}/expenses", status_code=201)
def create_expense(gid: int, body: ExpenseIn):
    with Session(engine) as s:
        get_group(s, gid)
        amount = pesewas(body.amount)
        ids = member_ids(s, gid)
        if body.paid_by not in ids:
            raise HTTPException(422, "payer is not in the group")
        if not body.shared_between:
            raise HTTPException(422, "shared_between must not be empty")
        if len(set(body.shared_between)) != len(body.shared_between):
            raise HTTPException(422, "duplicate members in shared_between")
        if any(i not in ids for i in body.shared_between):
            raise HTTPException(422, "shared_between has someone not in the group")
        e = Expense(group_id=gid, paid_by=body.paid_by, amount=amount,
                    description=body.description)
        s.add(e)
        s.commit()
        s.refresh(e)
        n = len(body.shared_between)
        base, extra = divmod(amount, n)
        shares = []
        for i, mid in enumerate(sorted(body.shared_between)):
            sh = base + (1 if i < extra else 0)
            s.add(ExpenseShare(expense_id=e.id, member_id=mid, share=sh))
            shares.append({"member_id": mid, "share": cedis(sh)})
        s.commit()
        return {"id": e.id, "paid_by": e.paid_by, "amount": cedis(amount),
                "description": e.description, "shares": shares}


@app.post("/groups/{gid}/payments", status_code=201)
def create_payment(gid: int, body: PaymentIn):
    with Session(engine) as s:
        get_group(s, gid)
        amount = pesewas(body.amount)
        ids = member_ids(s, gid)
        if body.from_member not in ids or body.to_member not in ids:
            raise HTTPException(422, "both members must be in the group")
        if body.from_member == body.to_member:
            raise HTTPException(422, "nobody can pay themselves back")
        p = Payment(group_id=gid, from_member=body.from_member,
                    to_member=body.to_member, amount=amount)
        s.add(p)
        s.commit()
        s.refresh(p)
        return {"id": p.id, "from_member": p.from_member,
                "to_member": p.to_member, "amount": cedis(amount)}


@app.get("/groups/{gid}/balances")
def balances(gid: int):
    with Session(engine) as s:
        get_group(s, gid)
        ms = s.exec(select(Member).where(Member.group_id == gid).order_by(Member.id)).all()
        bal = {m.id: 0 for m in ms}
        for e in s.exec(select(Expense).where(Expense.group_id == gid)):
            bal[e.paid_by] += e.amount
            for sh in s.exec(select(ExpenseShare).where(ExpenseShare.expense_id == e.id)):
                bal[sh.member_id] -= sh.share
        for p in s.exec(select(Payment).where(Payment.group_id == gid)):
            bal[p.from_member] += p.amount
            bal[p.to_member] -= p.amount
        return [{"member_id": m.id, "name": m.name, "balance": cedis(bal[m.id])}
                for m in ms]
