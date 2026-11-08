from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///./splitter.db", connect_args={"check_same_thread": False})


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
    paid_by_id: int
    amount_pesewas: int
    description: str = ""


class ExpenseShare(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    expense_id: int = Field(index=True)
    member_id: int
    share_pesewas: int


class Repayment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(index=True)
    from_id: int
    to_id: int
    amount_pesewas: int


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Shared costs", lifespan=lifespan)


def get_session():
    with Session(engine) as s:
        yield s


class GroupIn(BaseModel):
    name: str


class MemberIn(BaseModel):
    name: str


class ExpenseIn(BaseModel):
    paid_by: str
    amount: Decimal
    shared_between: List[str]
    description: str = ""


class RepaymentIn(BaseModel):
    from_member: str
    to_member: str
    amount: Decimal


def cedis(p: int) -> float:
    return float(Decimal(p) / 100)


def to_pesewas(amount: Decimal) -> int:
    try:
        p = amount * 100
        if not p.is_finite() or p != p.to_integral_value():
            raise HTTPException(422, "Amount can have at most 2 decimal places (pesewas)")
    except InvalidOperation:
        raise HTTPException(422, "Invalid amount")
    p = int(p)
    if p <= 0:
        raise HTTPException(422, "Amount must be more than zero")
    return p


def get_group(s: Session, group_id: int) -> Group:
    g = s.get(Group, group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    return g


def find_member(s: Session, group_id: int, name: str) -> Member:
    m = s.exec(select(Member).where(Member.group_id == group_id, Member.name == name.strip())).first()
    if not m:
        raise HTTPException(422, f"'{name}' is not a member of this group")
    return m


def member_out(m: Member):
    return {"id": m.id, "name": m.name}


def group_out(s: Session, g: Group):
    members = s.exec(select(Member).where(Member.group_id == g.id).order_by(Member.id)).all()
    return {"id": g.id, "name": g.name, "members": [member_out(m) for m in members]}


def expense_out(s: Session, e: Expense):
    shares = s.exec(select(ExpenseShare).where(ExpenseShare.expense_id == e.id).order_by(ExpenseShare.id)).all()
    payer = s.get(Member, e.paid_by_id)
    return {
        "id": e.id,
        "paid_by": payer.name,
        "amount": cedis(e.amount_pesewas),
        "description": e.description,
        "shares": [{"member": s.get(Member, sh.member_id).name, "amount": cedis(sh.share_pesewas)} for sh in shares],
    }


def repayment_out(s: Session, r: Repayment):
    return {
        "id": r.id,
        "from_member": s.get(Member, r.from_id).name,
        "to_member": s.get(Member, r.to_id).name,
        "amount": cedis(r.amount_pesewas),
    }


@app.post("/groups", status_code=201)
def create_group(body: GroupIn, s: Session = Depends(get_session)):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Group name is required")
    g = Group(name=name)
    s.add(g)
    s.commit()
    s.refresh(g)
    return group_out(s, g)


@app.get("/groups")
def list_groups(s: Session = Depends(get_session)):
    return [group_out(s, g) for g in s.exec(select(Group).order_by(Group.id)).all()]


@app.get("/groups/{group_id}")
def read_group(group_id: int, s: Session = Depends(get_session)):
    return group_out(s, get_group(s, group_id))


@app.post("/groups/{group_id}/members", status_code=201)
def add_member(group_id: int, body: MemberIn, s: Session = Depends(get_session)):
    get_group(s, group_id)
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Member name is required")
    if s.exec(select(Member).where(Member.group_id == group_id, Member.name == name)).first():
        raise HTTPException(409, "A member with this name is already in the group")
    m = Member(group_id=group_id, name=name)
    s.add(m)
    s.commit()
    s.refresh(m)
    return member_out(m)


@app.get("/groups/{group_id}/members")
def list_members(group_id: int, s: Session = Depends(get_session)):
    return group_out(s, get_group(s, group_id))["members"]


@app.post("/groups/{group_id}/expenses", status_code=201)
def add_expense(group_id: int, body: ExpenseIn, s: Session = Depends(get_session)):
    get_group(s, group_id)
    total = to_pesewas(body.amount)
    payer = find_member(s, group_id, body.paid_by)
    if not body.shared_between:
        raise HTTPException(422, "The expense must be shared between at least one member")
    sharers = [find_member(s, group_id, n) for n in body.shared_between]
    if len({m.id for m in sharers}) != len(sharers):
        raise HTTPException(422, "A member is listed more than once in shared_between")
    n = len(sharers)
    base, extra = divmod(total, n)
    e = Expense(group_id=group_id, paid_by_id=payer.id, amount_pesewas=total, description=body.description)
    s.add(e)
    s.commit()
    s.refresh(e)
    for i, m in enumerate(sharers):
        s.add(ExpenseShare(expense_id=e.id, member_id=m.id, share_pesewas=base + (1 if i < extra else 0)))
    s.commit()
    return expense_out(s, e)


@app.get("/groups/{group_id}/expenses")
def list_expenses(group_id: int, s: Session = Depends(get_session)):
    get_group(s, group_id)
    es = s.exec(select(Expense).where(Expense.group_id == group_id).order_by(Expense.id)).all()
    return [expense_out(s, e) for e in es]


@app.post("/groups/{group_id}/repayments", status_code=201)
def add_repayment(group_id: int, body: RepaymentIn, s: Session = Depends(get_session)):
    get_group(s, group_id)
    amount = to_pesewas(body.amount)
    a = find_member(s, group_id, body.from_member)
    b = find_member(s, group_id, body.to_member)
    if a.id == b.id:
        raise HTTPException(422, "Nobody can pay themselves back")
    r = Repayment(group_id=group_id, from_id=a.id, to_id=b.id, amount_pesewas=amount)
    s.add(r)
    s.commit()
    s.refresh(r)
    return repayment_out(s, r)


@app.get("/groups/{group_id}/repayments")
def list_repayments(group_id: int, s: Session = Depends(get_session)):
    get_group(s, group_id)
    rs = s.exec(select(Repayment).where(Repayment.group_id == group_id).order_by(Repayment.id)).all()
    return [repayment_out(s, r) for r in rs]


@app.get("/groups/{group_id}/balances")
def balances(group_id: int, s: Session = Depends(get_session)):
    get_group(s, group_id)
    members = s.exec(select(Member).where(Member.group_id == group_id).order_by(Member.id)).all()
    bal = {m.id: 0 for m in members}
    for e in s.exec(select(Expense).where(Expense.group_id == group_id)).all():
        bal[e.paid_by_id] += e.amount_pesewas
        for sh in s.exec(select(ExpenseShare).where(ExpenseShare.expense_id == e.id)).all():
            bal[sh.member_id] -= sh.share_pesewas
    for r in s.exec(select(Repayment).where(Repayment.group_id == group_id)).all():
        bal[r.from_id] += r.amount_pesewas
        bal[r.to_id] -= r.amount_pesewas
    return [{"member": m.name, "balance": cedis(bal[m.id])} for m in members]
