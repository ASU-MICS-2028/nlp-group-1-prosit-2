from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///./app.db", connect_args={"check_same_thread": False})


# ---------- database tables ----------
class Group(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class Member(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    name: str


class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    paid_by: int = Field(foreign_key="member.id")
    amount_pesewas: int
    created_at: datetime


class ExpenseShare(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    expense_id: int = Field(foreign_key="expense.id", index=True)
    member_id: int = Field(foreign_key="member.id")
    share_pesewas: int


class Repayment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    from_member: int = Field(foreign_key="member.id")
    to_member: int = Field(foreign_key="member.id")
    amount_pesewas: int
    created_at: datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Shared costs tracker", lifespan=lifespan)


# ---------- helpers ----------
def to_pesewas(v: Any) -> int:
    if isinstance(v, bool) or v is None:
        raise ValueError("amount must be a number in cedis")
    try:
        d = Decimal(str(v).strip())
    except (InvalidOperation, ValueError):
        raise ValueError("amount must be a number in cedis")
    if not d.is_finite():
        raise ValueError("amount must be a number in cedis")
    if d <= 0:
        raise ValueError("amount must be more than zero")
    if d != d.quantize(Decimal("0.01")):
        raise ValueError("amount cannot include fractions of a pesewa")
    return int(d * 100)


def cedis(p: int) -> float:
    return round(p / 100, 2)


def get_group(session: Session, group_id: int) -> Group:
    g = session.get(Group, group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    return g


def group_members(session: Session, group_id: int) -> List[Member]:
    return list(session.exec(select(Member).where(Member.group_id == group_id).order_by(Member.id)))


# ---------- request bodies ----------
class MemberIn(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_ok(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name is required")
        return v


class ExpenseIn(BaseModel):
    paid_by: int
    amount: Any
    shared_between: List[int]

    @field_validator("amount", mode="before")
    @classmethod
    def amount_ok(cls, v):
        return to_pesewas(v)


class RepaymentIn(BaseModel):
    from_member: int
    to_member: int
    amount: Any

    @field_validator("amount", mode="before")
    @classmethod
    def amount_ok(cls, v):
        return to_pesewas(v)


# ---------- output helpers ----------
def member_out(m: Member) -> dict:
    return {"member_number": m.id, "name": m.name}


def expense_out(session: Session, e: Expense, names: dict) -> dict:
    shares = session.exec(
        select(ExpenseShare).where(ExpenseShare.expense_id == e.id).order_by(ExpenseShare.id)
    ).all()
    return {
        "expense_number": e.id,
        "group_number": e.group_id,
        "paid_by": e.paid_by,
        "paid_by_name": names.get(e.paid_by),
        "amount": cedis(e.amount_pesewas),
        "shares": [
            {"member_number": s.member_id, "name": names.get(s.member_id), "share": cedis(s.share_pesewas)}
            for s in shares
        ],
        "created_at": e.created_at.isoformat(),
    }


def repayment_out(r: Repayment, names: dict) -> dict:
    return {
        "repayment_number": r.id,
        "group_number": r.group_id,
        "from_member": r.from_member,
        "from_name": names.get(r.from_member),
        "to_member": r.to_member,
        "to_name": names.get(r.to_member),
        "amount": cedis(r.amount_pesewas),
        "created_at": r.created_at.isoformat(),
    }


# ---------- endpoints ----------
@app.post("/groups", status_code=201)
def create_group():
    with Session(engine) as s:
        g = Group()
        s.add(g)
        s.commit()
        s.refresh(g)
        return {"group_number": g.id, "members": []}


@app.get("/groups/{group_number}")
def read_group(group_number: int):
    with Session(engine) as s:
        get_group(s, group_number)
        return {"group_number": group_number, "members": [member_out(m) for m in group_members(s, group_number)]}


@app.post("/groups/{group_number}/members", status_code=201)
def add_member(group_number: int, body: MemberIn):
    with Session(engine) as s:
        get_group(s, group_number)
        m = Member(group_id=group_number, name=body.name)
        s.add(m)
        s.commit()
        s.refresh(m)
        return {"group_number": group_number, **member_out(m)}


@app.post("/groups/{group_number}/expenses", status_code=201)
def add_expense(group_number: int, body: ExpenseIn):
    with Session(engine) as s:
        get_group(s, group_number)
        names = {m.id: m.name for m in group_members(s, group_number)}
        if body.paid_by not in names:
            raise HTTPException(400, "The payer is not a member of this group")
        if not body.shared_between:
            raise HTTPException(400, "An expense must be shared between at least one member")
        if len(set(body.shared_between)) != len(body.shared_between):
            raise HTTPException(400, "The same member is listed more than once")
        for mid in body.shared_between:
            if mid not in names:
                raise HTTPException(400, f"Member {mid} is not a member of this group")
        total = body.amount
        n = len(body.shared_between)
        base, extra = divmod(total, n)
        e = Expense(group_id=group_number, paid_by=body.paid_by, amount_pesewas=total,
                    created_at=datetime.now(timezone.utc))
        s.add(e)
        s.flush()
        for i, mid in enumerate(body.shared_between):
            s.add(ExpenseShare(expense_id=e.id, member_id=mid, share_pesewas=base + (1 if i < extra else 0)))
        s.commit()
        s.refresh(e)
        return expense_out(s, e, names)


@app.get("/groups/{group_number}/expenses")
def list_expenses(group_number: int):
    with Session(engine) as s:
        get_group(s, group_number)
        names = {m.id: m.name for m in group_members(s, group_number)}
        es = s.exec(select(Expense).where(Expense.group_id == group_number).order_by(Expense.id)).all()
        return [expense_out(s, e, names) for e in es]


@app.post("/groups/{group_number}/repayments", status_code=201)
def add_repayment(group_number: int, body: RepaymentIn):
    with Session(engine) as s:
        get_group(s, group_number)
        names = {m.id: m.name for m in group_members(s, group_number)}
        if body.from_member not in names:
            raise HTTPException(400, "The person paying back is not a member of this group")
        if body.to_member not in names:
            raise HTTPException(400, "The person receiving is not a member of this group")
        if body.from_member == body.to_member:
            raise HTTPException(400, "Nobody can pay themselves back")
        r = Repayment(group_id=group_number, from_member=body.from_member, to_member=body.to_member,
                      amount_pesewas=body.amount, created_at=datetime.now(timezone.utc))
        s.add(r)
        s.commit()
        s.refresh(r)
        return repayment_out(r, names)


@app.get("/groups/{group_number}/repayments")
def list_repayments(group_number: int):
    with Session(engine) as s:
        get_group(s, group_number)
        names = {m.id: m.name for m in group_members(s, group_number)}
        rs = s.exec(select(Repayment).where(Repayment.group_id == group_number).order_by(Repayment.id)).all()
        return [repayment_out(r, names) for r in rs]


@app.get("/groups/{group_number}/balances")
def balances(group_number: int):
    with Session(engine) as s:
        get_group(s, group_number)
        members = group_members(s, group_number)
        bal = {m.id: 0 for m in members}
        for e in s.exec(select(Expense).where(Expense.group_id == group_number)).all():
            bal[e.paid_by] += e.amount_pesewas
            for sh in s.exec(select(ExpenseShare).where(ExpenseShare.expense_id == e.id)).all():
                bal[sh.member_id] -= sh.share_pesewas
        for r in s.exec(select(Repayment).where(Repayment.group_id == group_number)).all():
            bal[r.from_member] += r.amount_pesewas
            bal[r.to_member] -= r.amount_pesewas
        return {
            "group_number": group_number,
            "balances": [{"member_number": m.id, "name": m.name, "balance": cedis(bal[m.id])} for m in members],
        }
