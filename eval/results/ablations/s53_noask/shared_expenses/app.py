from contextlib import asynccontextmanager
from decimal import Decimal
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///./shared_costs.db", connect_args={"check_same_thread": False})


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
    description: str = ""


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
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Shared costs", lifespan=lifespan)


def to_pesewas(v) -> int:
    d = Decimal(str(v))
    if d <= 0:
        raise ValueError("amount must be more than zero")
    p = d * 100
    if p != p.to_integral_value():
        raise ValueError("amount cannot have more than 2 decimal places (pesewas)")
    return int(p)


def cedis(p: int) -> float:
    return round(p / 100, 2)


class GroupIn(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def nonempty(cls, v):
        if not v.strip():
            raise ValueError("name must not be empty")
        return v.strip()


class MemberIn(GroupIn):
    pass


class ExpenseIn(BaseModel):
    paid_by: int
    amount: Decimal
    shared_between: List[int]
    description: str = ""

    @field_validator("amount")
    @classmethod
    def amt(cls, v):
        to_pesewas(v)
        return v


class PaymentIn(BaseModel):
    from_member: int
    to_member: int
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def amt(cls, v):
        to_pesewas(v)
        return v


def get_group(s: Session, gid: int) -> Group:
    g = s.get(Group, gid)
    if not g:
        raise HTTPException(404, "group not found")
    return g


def group_member_ids(s: Session, gid: int) -> set:
    return set(s.exec(select(Member.id).where(Member.group_id == gid)).all())


def member_out(m: Member):
    return {"id": m.id, "group_id": m.group_id, "name": m.name}


def expense_out(s: Session, e: Expense):
    shares = s.exec(select(ExpenseShare).where(ExpenseShare.expense_id == e.id).order_by(ExpenseShare.member_id)).all()
    return {
        "id": e.id, "group_id": e.group_id, "paid_by": e.paid_by, "amount": cedis(e.amount_pesewas),
        "description": e.description,
        "shares": [{"member_id": sh.member_id, "amount": cedis(sh.share_pesewas)} for sh in shares],
    }


def payment_out(p: Payment):
    return {"id": p.id, "group_id": p.group_id, "from_member": p.from_member,
            "to_member": p.to_member, "amount": cedis(p.amount_pesewas)}


@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    with Session(engine) as s:
        g = Group(name=body.name)
        s.add(g); s.commit(); s.refresh(g)
        return {"id": g.id, "name": g.name}


@app.get("/groups")
def list_groups():
    with Session(engine) as s:
        return [{"id": g.id, "name": g.name} for g in s.exec(select(Group)).all()]


@app.get("/groups/{gid}")
def read_group(gid: int):
    with Session(engine) as s:
        g = get_group(s, gid)
        ms = s.exec(select(Member).where(Member.group_id == gid)).all()
        return {"id": g.id, "name": g.name, "members": [member_out(m) for m in ms]}


@app.post("/groups/{gid}/members", status_code=201)
def add_member(gid: int, body: MemberIn):
    with Session(engine) as s:
        get_group(s, gid)
        existing = s.exec(select(Member).where(Member.group_id == gid)).all()
        if any(m.name.lower() == body.name.lower() for m in existing):
            raise HTTPException(409, "a member with this name is already in the group")
        m = Member(group_id=gid, name=body.name)
        s.add(m); s.commit(); s.refresh(m)
        return member_out(m)


@app.get("/groups/{gid}/members")
def list_members(gid: int):
    with Session(engine) as s:
        get_group(s, gid)
        return [member_out(m) for m in s.exec(select(Member).where(Member.group_id == gid)).all()]


@app.post("/groups/{gid}/expenses", status_code=201)
def add_expense(gid: int, body: ExpenseIn):
    with Session(engine) as s:
        get_group(s, gid)
        ids = group_member_ids(s, gid)
        if body.paid_by not in ids:
            raise HTTPException(400, "the payer is not a member of this group")
        if not body.shared_between:
            raise HTTPException(400, "the expense must be shared between at least one member")
        if len(set(body.shared_between)) != len(body.shared_between):
            raise HTTPException(400, "a member is listed more than once")
        if any(m not in ids for m in body.shared_between):
            raise HTTPException(400, "everyone sharing the expense must be a member of this group")
        total = to_pesewas(body.amount)
        e = Expense(group_id=gid, paid_by=body.paid_by, amount_pesewas=total, description=body.description)
        s.add(e); s.commit(); s.refresh(e)
        members = sorted(body.shared_between)
        base, rem = divmod(total, len(members))
        for i, mid in enumerate(members):
            s.add(ExpenseShare(expense_id=e.id, member_id=mid, share_pesewas=base + (1 if i < rem else 0)))
        s.commit()
        return expense_out(s, e)


@app.get("/groups/{gid}/expenses")
def list_expenses(gid: int):
    with Session(engine) as s:
        get_group(s, gid)
        return [expense_out(s, e) for e in s.exec(select(Expense).where(Expense.group_id == gid)).all()]


@app.post("/groups/{gid}/payments", status_code=201)
def add_payment(gid: int, body: PaymentIn):
    with Session(engine) as s:
        get_group(s, gid)
        ids = group_member_ids(s, gid)
        if body.from_member not in ids or body.to_member not in ids:
            raise HTTPException(400, "both people must be members of this group")
        if body.from_member == body.to_member:
            raise HTTPException(400, "nobody can pay themselves back")
        p = Payment(group_id=gid, from_member=body.from_member, to_member=body.to_member,
                    amount_pesewas=to_pesewas(body.amount))
        s.add(p); s.commit(); s.refresh(p)
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
        ms = s.exec(select(Member).where(Member.group_id == gid)).all()
        bal = {m.id: 0 for m in ms}
        for e in s.exec(select(Expense).where(Expense.group_id == gid)).all():
            bal[e.paid_by] += e.amount_pesewas
            for sh in s.exec(select(ExpenseShare).where(ExpenseShare.expense_id == e.id)).all():
                bal[sh.member_id] -= sh.share_pesewas
        for p in s.exec(select(Payment).where(Payment.group_id == gid)).all():
            bal[p.from_member] += p.amount_pesewas
            bal[p.to_member] -= p.amount_pesewas
        return [{"member_id": m.id, "name": m.name, "balance": cedis(bal[m.id])} for m in ms]
