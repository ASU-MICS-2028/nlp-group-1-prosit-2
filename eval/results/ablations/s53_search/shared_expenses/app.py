from contextlib import asynccontextmanager
from decimal import Decimal
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///./group_costs.db", connect_args={"check_same_thread": False})


class Group(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class Member(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    name: str


class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    paid_by: int = Field(foreign_key="member.id")
    amount_pesewas: int


class ExpenseShare(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    expense_id: int = Field(foreign_key="expense.id", index=True)
    member_id: int = Field(foreign_key="member.id")
    share_pesewas: int


class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    from_member: int = Field(foreign_key="member.id")
    to_member: int = Field(foreign_key="member.id")
    amount_pesewas: int


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Shared costs", lifespan=lifespan)


class GroupIn(BaseModel):
    name: str


class MemberIn(BaseModel):
    name: str


class ExpenseIn(BaseModel):
    paid_by: int
    amount: Decimal
    shared_between: List[int]


class PaymentIn(BaseModel):
    from_member: int
    to_member: int
    amount: Decimal


def cedis(p: int) -> float:
    return round(p / 100, 2)


def to_pesewas(amount: Decimal) -> int:
    if not amount.is_finite():
        raise HTTPException(422, "Amount must be a number")
    if amount <= 0:
        raise HTTPException(422, "Amount must be more than zero")
    p = amount * 100
    if p != p.to_integral_value():
        raise HTTPException(422, "Amount can have at most 2 decimal places (pesewas)")
    return int(p)


def get_group(s: Session, gid: int) -> Group:
    g = s.get(Group, gid)
    if not g:
        raise HTTPException(404, "Group not found")
    return g


def check_member(s: Session, gid: int, mid: int) -> Member:
    m = s.get(Member, mid)
    if not m or m.group_id != gid:
        raise HTTPException(422, f"Member {mid} is not in this group")
    return m


def member_out(m: Member):
    return {"id": m.id, "group_id": m.group_id, "name": m.name}


def expense_out(s: Session, e: Expense):
    shares = s.exec(select(ExpenseShare).where(ExpenseShare.expense_id == e.id)).all()
    return {
        "id": e.id, "group_id": e.group_id, "paid_by": e.paid_by,
        "amount": cedis(e.amount_pesewas),
        "shares": [{"member_id": sh.member_id, "amount": cedis(sh.share_pesewas)} for sh in shares],
    }


def payment_out(p: Payment):
    return {"id": p.id, "group_id": p.group_id, "from_member": p.from_member,
            "to_member": p.to_member, "amount": cedis(p.amount_pesewas)}


@app.post("/groups", status_code=201)
def create_group(data: GroupIn):
    name = data.name.strip()
    if not name:
        raise HTTPException(422, "Group name is required")
    with Session(engine) as s:
        g = Group(name=name)
        s.add(g)
        s.commit()
        s.refresh(g)
        return {"id": g.id, "name": g.name}


@app.get("/groups/{gid}")
def read_group(gid: int):
    with Session(engine) as s:
        g = get_group(s, gid)
        members = s.exec(select(Member).where(Member.group_id == gid)).all()
        return {"id": g.id, "name": g.name, "members": [member_out(m) for m in members]}


@app.post("/groups/{gid}/members", status_code=201)
def add_member(gid: int, data: MemberIn):
    name = data.name.strip()
    if not name:
        raise HTTPException(422, "Member name is required")
    with Session(engine) as s:
        get_group(s, gid)
        existing = s.exec(select(Member).where(Member.group_id == gid)).all()
        if any(m.name.lower() == name.lower() for m in existing):
            raise HTTPException(409, "A member with this name is already in the group")
        m = Member(group_id=gid, name=name)
        s.add(m)
        s.commit()
        s.refresh(m)
        return member_out(m)


@app.get("/groups/{gid}/members")
def list_members(gid: int):
    with Session(engine) as s:
        get_group(s, gid)
        return [member_out(m) for m in s.exec(select(Member).where(Member.group_id == gid)).all()]


@app.post("/groups/{gid}/expenses", status_code=201)
def add_expense(gid: int, data: ExpenseIn):
    with Session(engine) as s:
        get_group(s, gid)
        total = to_pesewas(data.amount)
        check_member(s, gid, data.paid_by)
        if not data.shared_between:
            raise HTTPException(422, "The expense must be shared between at least one member")
        if len(set(data.shared_between)) != len(data.shared_between):
            raise HTTPException(422, "A member is listed more than once")
        for mid in data.shared_between:
            check_member(s, gid, mid)
        e = Expense(group_id=gid, paid_by=data.paid_by, amount_pesewas=total)
        s.add(e)
        s.flush()
        n = len(data.shared_between)
        base, extra = divmod(total, n)
        for i, mid in enumerate(data.shared_between):
            s.add(ExpenseShare(expense_id=e.id, member_id=mid,
                               share_pesewas=base + (1 if i < extra else 0)))
        s.commit()
        s.refresh(e)
        return expense_out(s, e)


@app.get("/groups/{gid}/expenses")
def list_expenses(gid: int):
    with Session(engine) as s:
        get_group(s, gid)
        return [expense_out(s, e) for e in s.exec(select(Expense).where(Expense.group_id == gid)).all()]


@app.post("/groups/{gid}/payments", status_code=201)
def add_payment(gid: int, data: PaymentIn):
    with Session(engine) as s:
        get_group(s, gid)
        amount = to_pesewas(data.amount)
        check_member(s, gid, data.from_member)
        check_member(s, gid, data.to_member)
        if data.from_member == data.to_member:
            raise HTTPException(422, "Nobody can pay themselves back")
        p = Payment(group_id=gid, from_member=data.from_member, to_member=data.to_member,
                    amount_pesewas=amount)
        s.add(p)
        s.commit()
        s.refresh(p)
        return payment_out(p)


@app.get("/groups/{gid}/payments")
def list_payments(gid: int):
    with Session(engine) as s:
        get_group(s, gid)
        return [payment_out(p) for p in s.exec(select(Payment).where(Payment.group_id == gid)).all()]


@app.get("/groups/{gid}/balances")
def balances(gid: int):
    with Session(engine) as s:
        get_group(s, gid)
        members = s.exec(select(Member).where(Member.group_id == gid)).all()
        bal = {m.id: 0 for m in members}
        for e in s.exec(select(Expense).where(Expense.group_id == gid)).all():
            bal[e.paid_by] += e.amount_pesewas
            for sh in s.exec(select(ExpenseShare).where(ExpenseShare.expense_id == e.id)).all():
                bal[sh.member_id] -= sh.share_pesewas
        for p in s.exec(select(Payment).where(Payment.group_id == gid)).all():
            bal[p.from_member] += p.amount_pesewas
            bal[p.to_member] -= p.amount_pesewas
        return [{"member_id": m.id, "name": m.name, "balance": cedis(bal[m.id])} for m in members]
