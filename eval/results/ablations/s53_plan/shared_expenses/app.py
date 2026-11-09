from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///./splitter.db", connect_args={"check_same_thread": False})


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
    description: Optional[str] = None
    created_at: datetime


class ExpenseShare(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    expense_id: int = Field(foreign_key="expense.id", index=True)
    member_id: int = Field(foreign_key="member.id")
    share_pesewas: int


class Repayment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    from_member_id: int = Field(foreign_key="member.id")
    to_member_id: int = Field(foreign_key="member.id")
    amount_pesewas: int
    created_at: datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Shared Costs", lifespan=lifespan)


# ---------- request bodies ----------

class GroupIn(BaseModel):
    name: str


class MemberIn(BaseModel):
    name: str


class ExpenseIn(BaseModel):
    paid_by: int
    amount: Decimal
    description: Optional[str] = None
    shared_between: List[int]


class RepaymentIn(BaseModel):
    from_member_id: int
    to_member_id: int
    amount: Decimal


# ---------- helpers ----------

def to_pesewas(amount: Decimal) -> int:
    if not amount.is_finite():
        raise HTTPException(422, "Amount must be a number.")
    if amount <= 0:
        raise HTTPException(422, "Amount must be more than zero.")
    if amount.as_tuple().exponent < -2 and amount != amount.quantize(Decimal("0.01")):
        raise HTTPException(422, "Amount cannot be finer than one pesewa (two decimal places).")
    return int(amount * 100)


def cedis(p: int) -> float:
    return float(Decimal(p) / 100)


def get_group(session: Session, group_id: int) -> Group:
    g = session.get(Group, group_id)
    if not g:
        raise HTTPException(404, "Group not found.")
    return g


def member_ids(session: Session, group_id: int) -> set:
    return set(session.exec(select(Member.id).where(Member.group_id == group_id)).all())


def now():
    return datetime.now(timezone.utc)


def expense_out(session: Session, e: Expense) -> dict:
    shares = session.exec(select(ExpenseShare).where(ExpenseShare.expense_id == e.id)
                          .order_by(ExpenseShare.id)).all()
    return {
        "id": e.id,
        "group_id": e.group_id,
        "paid_by": e.paid_by,
        "amount": cedis(e.amount_pesewas),
        "description": e.description,
        "shared_between": [s.member_id for s in shares],
        "shares": [{"member_id": s.member_id, "share": cedis(s.share_pesewas)} for s in shares],
        "created_at": e.created_at.isoformat(),
    }


def repayment_out(r: Repayment) -> dict:
    return {
        "id": r.id,
        "group_id": r.group_id,
        "from_member_id": r.from_member_id,
        "to_member_id": r.to_member_id,
        "amount": cedis(r.amount_pesewas),
        "created_at": r.created_at.isoformat(),
    }


# ---------- endpoints ----------

@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Group name is required.")
    with Session(engine) as s:
        g = Group(name=name)
        s.add(g)
        s.commit()
        s.refresh(g)
        return {"id": g.id, "name": g.name, "members": []}


@app.get("/groups/{group_id}")
def read_group(group_id: int):
    with Session(engine) as s:
        g = get_group(s, group_id)
        members = s.exec(select(Member).where(Member.group_id == group_id).order_by(Member.id)).all()
        return {"id": g.id, "name": g.name,
                "members": [{"id": m.id, "name": m.name} for m in members]}


@app.post("/groups/{group_id}/members", status_code=201)
def add_member(group_id: int, body: MemberIn):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Member name is required.")
    with Session(engine) as s:
        get_group(s, group_id)
        m = Member(group_id=group_id, name=name)
        s.add(m)
        s.commit()
        s.refresh(m)
        return {"id": m.id, "group_id": m.group_id, "name": m.name}


@app.post("/groups/{group_id}/expenses", status_code=201)
def add_expense(group_id: int, body: ExpenseIn):
    with Session(engine) as s:
        get_group(s, group_id)
        total = to_pesewas(body.amount)
        ids = member_ids(s, group_id)
        if body.paid_by not in ids:
            raise HTTPException(422, "The payer is not a member of this group.")
        if not body.shared_between:
            raise HTTPException(422, "An expense must be shared between at least one member.")
        if len(set(body.shared_between)) != len(body.shared_between):
            raise HTTPException(422, "A member is listed more than once among those sharing.")
        for mid in body.shared_between:
            if mid not in ids:
                raise HTTPException(422, f"Member {mid} is not a member of this group.")
        n = len(body.shared_between)
        base, extra = divmod(total, n)
        e = Expense(group_id=group_id, paid_by=body.paid_by, amount_pesewas=total,
                    description=body.description, created_at=now())
        s.add(e)
        s.flush()
        for i, mid in enumerate(body.shared_between):
            s.add(ExpenseShare(expense_id=e.id, member_id=mid,
                               share_pesewas=base + (1 if i < extra else 0)))
        s.commit()
        s.refresh(e)
        return expense_out(s, e)


@app.get("/groups/{group_id}/expenses")
def list_expenses(group_id: int):
    with Session(engine) as s:
        get_group(s, group_id)
        es = s.exec(select(Expense).where(Expense.group_id == group_id).order_by(Expense.id)).all()
        return [expense_out(s, e) for e in es]


@app.post("/groups/{group_id}/repayments", status_code=201)
def add_repayment(group_id: int, body: RepaymentIn):
    with Session(engine) as s:
        get_group(s, group_id)
        amount = to_pesewas(body.amount)
        ids = member_ids(s, group_id)
        if body.from_member_id not in ids:
            raise HTTPException(422, "The person paying back is not a member of this group.")
        if body.to_member_id not in ids:
            raise HTTPException(422, "The person receiving is not a member of this group.")
        if body.from_member_id == body.to_member_id:
            raise HTTPException(422, "Nobody can pay themselves back.")
        r = Repayment(group_id=group_id, from_member_id=body.from_member_id,
                      to_member_id=body.to_member_id, amount_pesewas=amount, created_at=now())
        s.add(r)
        s.commit()
        s.refresh(r)
        return repayment_out(r)


@app.get("/groups/{group_id}/repayments")
def list_repayments(group_id: int):
    with Session(engine) as s:
        get_group(s, group_id)
        rs = s.exec(select(Repayment).where(Repayment.group_id == group_id).order_by(Repayment.id)).all()
        return [repayment_out(r) for r in rs]


@app.get("/groups/{group_id}/balances")
def balances(group_id: int):
    with Session(engine) as s:
        get_group(s, group_id)
        members = s.exec(select(Member).where(Member.group_id == group_id).order_by(Member.id)).all()
        bal = {m.id: 0 for m in members}
        for e in s.exec(select(Expense).where(Expense.group_id == group_id)).all():
            bal[e.paid_by] += e.amount_pesewas
            for sh in s.exec(select(ExpenseShare).where(ExpenseShare.expense_id == e.id)).all():
                bal[sh.member_id] -= sh.share_pesewas
        for r in s.exec(select(Repayment).where(Repayment.group_id == group_id)).all():
            bal[r.from_member_id] += r.amount_pesewas
            bal[r.to_member_id] -= r.amount_pesewas
        return [{"member_id": m.id, "name": m.name, "balance": cedis(bal[m.id])} for m in members]
