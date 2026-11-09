from contextlib import asynccontextmanager
from decimal import Decimal
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///./costs.db", connect_args={"check_same_thread": False})

MAX_PESEWAS = 100_000_000_000  # 1 billion cedis


# ---------- database tables ----------
class Group(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class Member(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(index=True, foreign_key="group.id")
    name: str


class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(index=True, foreign_key="group.id")
    paid_by: int = Field(foreign_key="member.id")
    amount_pesewas: int
    description: Optional[str] = None


class ExpenseShare(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    expense_id: int = Field(index=True, foreign_key="expense.id")
    member_id: int = Field(foreign_key="member.id")
    amount_pesewas: int


class Repayment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(index=True, foreign_key="group.id")
    from_member: int = Field(foreign_key="member.id")
    to_member: int = Field(foreign_key="member.id")
    amount_pesewas: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Shared costs", lifespan=lifespan)


# ---------- helpers ----------
def to_pesewas(value: Decimal) -> int:
    if value <= 0:
        raise ValueError("amount must be more than zero")
    if value.as_tuple().exponent < -2 and value != value.quantize(Decimal("0.01")):
        raise ValueError("amount can have at most 2 decimal places (pesewas)")
    p = int(value * 100)
    if p > MAX_PESEWAS:
        raise ValueError("amount is too large")
    return p


def cedis(p: int) -> float:
    return round(p / 100, 2)


def clean_name(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("name must not be empty")
    return v


def get_group(session: Session, group_id: int) -> Group:
    g = session.get(Group, group_id)
    if not g:
        raise HTTPException(404, "group not found")
    return g


def check_member(session: Session, group_id: int, member_id: int, label: str) -> Member:
    m = session.get(Member, member_id)
    if not m or m.group_id != group_id:
        raise HTTPException(422, f"{label} (member {member_id}) is not in this group")
    return m


# ---------- request bodies ----------
class GroupIn(BaseModel):
    name: str
    _n = field_validator("name")(clean_name)


class MemberIn(BaseModel):
    name: str
    _n = field_validator("name")(clean_name)


class ExpenseIn(BaseModel):
    paid_by: int
    amount: Decimal
    shared_between: List[int]
    description: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def _amount(cls, v):
        to_pesewas(v)
        return v

    @field_validator("shared_between")
    @classmethod
    def _shared(cls, v):
        if not v:
            raise ValueError("must list at least one member")
        if len(set(v)) != len(v):
            raise ValueError("a member is listed more than once")
        return v


class RepaymentIn(BaseModel):
    from_member: int
    to_member: int
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def _amount(cls, v):
        to_pesewas(v)
        return v


# ---------- output helpers ----------
def group_out(g: Group):
    return {"id": g.id, "name": g.name}


def member_out(m: Member):
    return {"id": m.id, "group_id": m.group_id, "name": m.name}


def expense_out(session: Session, e: Expense):
    shares = session.exec(select(ExpenseShare).where(ExpenseShare.expense_id == e.id)).all()
    return {
        "id": e.id,
        "group_id": e.group_id,
        "paid_by": e.paid_by,
        "amount": cedis(e.amount_pesewas),
        "description": e.description,
        "shares": [{"member_id": s.member_id, "amount": cedis(s.amount_pesewas)} for s in shares],
    }


def repayment_out(r: Repayment):
    return {
        "id": r.id,
        "group_id": r.group_id,
        "from_member": r.from_member,
        "to_member": r.to_member,
        "amount": cedis(r.amount_pesewas),
    }


# ---------- endpoints ----------
@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    with Session(engine) as s:
        g = Group(name=body.name)
        s.add(g)
        s.commit()
        s.refresh(g)
        return group_out(g)


@app.get("/groups/{group_id}")
def read_group(group_id: int):
    with Session(engine) as s:
        g = get_group(s, group_id)
        members = s.exec(select(Member).where(Member.group_id == group_id)).all()
        return {**group_out(g), "members": [member_out(m) for m in members]}


@app.post("/groups/{group_id}/members", status_code=201)
def add_member(group_id: int, body: MemberIn):
    with Session(engine) as s:
        get_group(s, group_id)
        existing = s.exec(select(Member).where(Member.group_id == group_id)).all()
        if any(m.name.lower() == body.name.lower() for m in existing):
            raise HTTPException(409, "a member with this name is already in the group")
        m = Member(group_id=group_id, name=body.name)
        s.add(m)
        s.commit()
        s.refresh(m)
        return member_out(m)


@app.get("/groups/{group_id}/members")
def list_members(group_id: int):
    with Session(engine) as s:
        get_group(s, group_id)
        return [member_out(m) for m in s.exec(select(Member).where(Member.group_id == group_id)).all()]


@app.post("/groups/{group_id}/expenses", status_code=201)
def add_expense(group_id: int, body: ExpenseIn):
    with Session(engine) as s:
        get_group(s, group_id)
        check_member(s, group_id, body.paid_by, "payer")
        for mid in body.shared_between:
            check_member(s, group_id, mid, "sharer")
        total = to_pesewas(body.amount)
        n = len(body.shared_between)
        base, extra = divmod(total, n)
        e = Expense(group_id=group_id, paid_by=body.paid_by, amount_pesewas=total,
                    description=body.description)
        s.add(e)
        s.flush()
        for i, mid in enumerate(body.shared_between):
            s.add(ExpenseShare(expense_id=e.id, member_id=mid,
                               amount_pesewas=base + (1 if i < extra else 0)))
        s.commit()
        s.refresh(e)
        return expense_out(s, e)


@app.get("/groups/{group_id}/expenses")
def list_expenses(group_id: int):
    with Session(engine) as s:
        get_group(s, group_id)
        es = s.exec(select(Expense).where(Expense.group_id == group_id)).all()
        return [expense_out(s, e) for e in es]


@app.post("/groups/{group_id}/repayments", status_code=201)
def add_repayment(group_id: int, body: RepaymentIn):
    with Session(engine) as s:
        get_group(s, group_id)
        check_member(s, group_id, body.from_member, "from_member")
        check_member(s, group_id, body.to_member, "to_member")
        if body.from_member == body.to_member:
            raise HTTPException(422, "a member cannot pay themselves back")
        r = Repayment(group_id=group_id, from_member=body.from_member,
                      to_member=body.to_member, amount_pesewas=to_pesewas(body.amount))
        s.add(r)
        s.commit()
        s.refresh(r)
        return repayment_out(r)


@app.get("/groups/{group_id}/repayments")
def list_repayments(group_id: int):
    with Session(engine) as s:
        get_group(s, group_id)
        rs = s.exec(select(Repayment).where(Repayment.group_id == group_id)).all()
        return [repayment_out(r) for r in rs]


@app.get("/groups/{group_id}/balances")
def balances(group_id: int):
    with Session(engine) as s:
        get_group(s, group_id)
        members = s.exec(select(Member).where(Member.group_id == group_id)).all()
        bal = {m.id: 0 for m in members}
        for e in s.exec(select(Expense).where(Expense.group_id == group_id)).all():
            bal[e.paid_by] += e.amount_pesewas
            for sh in s.exec(select(ExpenseShare).where(ExpenseShare.expense_id == e.id)).all():
                bal[sh.member_id] -= sh.amount_pesewas
        for r in s.exec(select(Repayment).where(Repayment.group_id == group_id)).all():
            bal[r.from_member] += r.amount_pesewas
            bal[r.to_member] -= r.amount_pesewas
        return [{"member_id": m.id, "name": m.name, "balance": cedis(bal[m.id])} for m in members]
