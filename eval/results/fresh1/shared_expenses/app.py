from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///splitwise.db", connect_args={"check_same_thread": False})


# ---------- database tables ----------
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
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Shared costs", lifespan=lifespan)


def get_session():
    with Session(engine) as session:
        yield session


# ---------- helpers ----------
def to_pesewas(value) -> int:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("amount must be a number")
    if not d.is_finite():
        raise ValueError("amount must be a number")
    if d <= 0:
        raise ValueError("amount must be more than zero")
    p = d * 100
    if p != p.to_integral_value():
        raise ValueError("amount can have at most 2 decimal places (pesewas)")
    return int(p)


def cedis(p: int) -> float:
    return float(Decimal(p) / 100)


def split(total: int, member_ids: List[int]) -> List[tuple]:
    base, rem = divmod(total, len(member_ids))
    return [(m, base + (1 if i < rem else 0)) for i, m in enumerate(member_ids)]


# ---------- request bodies ----------
class NameIn(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class AmountMixin(BaseModel):
    amount: Decimal

    @field_validator("amount", mode="before")
    @classmethod
    def check_amount(cls, v):
        if isinstance(v, bool):
            raise ValueError("amount must be a number")
        to_pesewas(v)
        return v


class ExpenseIn(AmountMixin):
    paid_by: int
    shared_between: List[int]
    description: str = ""


class PaymentIn(AmountMixin):
    from_member: int
    to_member: int


# ---------- output helpers ----------
def group_out(g: Group):
    return {"id": g.id, "name": g.name}


def member_out(m: Member):
    return {"id": m.id, "group_id": m.group_id, "name": m.name}


def expense_out(session: Session, e: Expense):
    shares = session.exec(select(ExpenseShare).where(ExpenseShare.expense_id == e.id).order_by(ExpenseShare.id)).all()
    return {
        "id": e.id,
        "group_id": e.group_id,
        "paid_by": e.paid_by,
        "amount": cedis(e.amount_pesewas),
        "description": e.description,
        "shares": [{"member_id": s.member_id, "amount": cedis(s.share_pesewas)} for s in shares],
    }


def payment_out(p: Payment):
    return {
        "id": p.id,
        "group_id": p.group_id,
        "from_member": p.from_member,
        "to_member": p.to_member,
        "amount": cedis(p.amount_pesewas),
    }


def load_group(session: Session, group_id: int) -> Group:
    g = session.get(Group, group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    return g


def require_member(session: Session, group_id: int, member_id: int, label: str):
    m = session.get(Member, member_id)
    if not m or m.group_id != group_id:
        raise HTTPException(400, f"{label} (member {member_id}) is not in this group")
    return m


# ---------- endpoints ----------
@app.post("/groups", status_code=201)
def create_group(body: NameIn, session: Session = Depends(get_session)):
    g = Group(name=body.name)
    session.add(g)
    session.commit()
    session.refresh(g)
    return group_out(g)


@app.get("/groups")
def list_groups(session: Session = Depends(get_session)):
    return [group_out(g) for g in session.exec(select(Group).order_by(Group.id)).all()]


@app.get("/groups/{group_id}")
def get_group(group_id: int, session: Session = Depends(get_session)):
    g = load_group(session, group_id)
    members = session.exec(select(Member).where(Member.group_id == group_id).order_by(Member.id)).all()
    return {**group_out(g), "members": [member_out(m) for m in members]}


@app.post("/groups/{group_id}/members", status_code=201)
def add_member(group_id: int, body: NameIn, session: Session = Depends(get_session)):
    load_group(session, group_id)
    existing = session.exec(select(Member).where(Member.group_id == group_id)).all()
    if any(m.name.lower() == body.name.lower() for m in existing):
        raise HTTPException(409, "A member with this name is already in the group")
    m = Member(group_id=group_id, name=body.name)
    session.add(m)
    session.commit()
    session.refresh(m)
    return member_out(m)


@app.get("/groups/{group_id}/members")
def list_members(group_id: int, session: Session = Depends(get_session)):
    load_group(session, group_id)
    members = session.exec(select(Member).where(Member.group_id == group_id).order_by(Member.id)).all()
    return [member_out(m) for m in members]


@app.post("/groups/{group_id}/expenses", status_code=201)
def add_expense(group_id: int, body: ExpenseIn, session: Session = Depends(get_session)):
    load_group(session, group_id)
    total = to_pesewas(body.amount)
    if not body.shared_between:
        raise HTTPException(400, "shared_between must list at least one member")
    if len(set(body.shared_between)) != len(body.shared_between):
        raise HTTPException(400, "shared_between must not list the same member twice")
    require_member(session, group_id, body.paid_by, "paid_by")
    for mid in body.shared_between:
        require_member(session, group_id, mid, "shared_between")
    e = Expense(group_id=group_id, paid_by=body.paid_by, amount_pesewas=total, description=body.description)
    session.add(e)
    session.flush()
    for mid, share in split(total, body.shared_between):
        session.add(ExpenseShare(expense_id=e.id, member_id=mid, share_pesewas=share))
    session.commit()
    session.refresh(e)
    return expense_out(session, e)


@app.get("/groups/{group_id}/expenses")
def list_expenses(group_id: int, session: Session = Depends(get_session)):
    load_group(session, group_id)
    es = session.exec(select(Expense).where(Expense.group_id == group_id).order_by(Expense.id)).all()
    return [expense_out(session, e) for e in es]


@app.post("/groups/{group_id}/payments", status_code=201)
def add_payment(group_id: int, body: PaymentIn, session: Session = Depends(get_session)):
    load_group(session, group_id)
    total = to_pesewas(body.amount)
    require_member(session, group_id, body.from_member, "from_member")
    require_member(session, group_id, body.to_member, "to_member")
    if body.from_member == body.to_member:
        raise HTTPException(400, "Nobody can pay themselves back")
    p = Payment(group_id=group_id, from_member=body.from_member, to_member=body.to_member, amount_pesewas=total)
    session.add(p)
    session.commit()
    session.refresh(p)
    return payment_out(p)


@app.get("/groups/{group_id}/payments")
def list_payments(group_id: int, session: Session = Depends(get_session)):
    load_group(session, group_id)
    ps = session.exec(select(Payment).where(Payment.group_id == group_id).order_by(Payment.id)).all()
    return [payment_out(p) for p in ps]


@app.get("/groups/{group_id}/balances")
def balances(group_id: int, session: Session = Depends(get_session)):
    load_group(session, group_id)
    members = session.exec(select(Member).where(Member.group_id == group_id).order_by(Member.id)).all()
    bal = {m.id: 0 for m in members}
    for e in session.exec(select(Expense).where(Expense.group_id == group_id)).all():
        bal[e.paid_by] += e.amount_pesewas
        for s in session.exec(select(ExpenseShare).where(ExpenseShare.expense_id == e.id)).all():
            bal[s.member_id] -= s.share_pesewas
    for p in session.exec(select(Payment).where(Payment.group_id == group_id)).all():
        bal[p.from_member] += p.amount_pesewas
        bal[p.to_member] -= p.amount_pesewas
    return [{"member_id": m.id, "name": m.name, "balance": cedis(bal[m.id])} for m in members]
