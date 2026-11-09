from decimal import Decimal
from typing import List, Optional

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
    group_id: int = Field(index=True)
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
    members: List[str] = []


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


def to_pesewas(amount: Decimal) -> int:
    if not amount.is_finite() or amount <= 0:
        raise HTTPException(422, "Amount must be more than zero")
    p = amount * 100
    if p != p.to_integral_value():
        raise HTTPException(422, "Amount cannot have fractions of a pesewa")
    return int(p)


def cedis(p: int) -> float:
    return p / 100


def clean_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise HTTPException(422, "Name cannot be empty")
    return name


def get_group(s: Session, gid: int) -> Group:
    g = s.get(Group, gid)
    if not g:
        raise HTTPException(404, "Group not found")
    return g


def members_of(s: Session, gid: int):
    return s.exec(select(Member).where(Member.group_id == gid).order_by(Member.id)).all()


def add_member(s: Session, gid: int, name: str) -> Member:
    name = clean_name(name)
    if any(m.name == name for m in members_of(s, gid)):
        raise HTTPException(409, "Member name already in group")
    m = Member(group_id=gid, name=name)
    s.add(m)
    s.flush()
    return m


def member_out(m: Member):
    return {"id": m.id, "name": m.name}


def group_out(s: Session, g: Group):
    return {"id": g.id, "name": g.name, "members": [member_out(m) for m in members_of(s, g.id)]}


@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    name = clean_name(body.name)
    names = [clean_name(n) for n in body.members]
    if len(set(names)) != len(names):
        raise HTTPException(422, "Duplicate member names")
    with Session(engine) as s:
        g = Group(name=name)
        s.add(g)
        s.flush()
        for n in names:
            add_member(s, g.id, n)
        s.commit()
        s.refresh(g)
        return group_out(s, g)


@app.get("/groups/{gid}")
def read_group(gid: int):
    with Session(engine) as s:
        return group_out(s, get_group(s, gid))


@app.post("/groups/{gid}/members", status_code=201)
def create_member(gid: int, body: MemberIn):
    with Session(engine) as s:
        get_group(s, gid)
        m = add_member(s, gid, body.name)
        s.commit()
        s.refresh(m)
        return member_out(m)


def check_member(s: Session, gid: int, mid: int) -> None:
    m = s.get(Member, mid)
    if not m or m.group_id != gid:
        raise HTTPException(422, f"Member {mid} is not in this group")


@app.post("/groups/{gid}/expenses", status_code=201)
def create_expense(gid: int, body: ExpenseIn):
    with Session(engine) as s:
        get_group(s, gid)
        total = to_pesewas(body.amount)
        if not body.shared_between:
            raise HTTPException(422, "Expense must be shared between someone")
        if len(set(body.shared_between)) != len(body.shared_between):
            raise HTTPException(422, "Duplicate members in shared_between")
        check_member(s, gid, body.paid_by)
        for mid in body.shared_between:
            check_member(s, gid, mid)
        e = Expense(group_id=gid, paid_by=body.paid_by, amount=total)
        s.add(e)
        s.flush()
        n = len(body.shared_between)
        base, extra = divmod(total, n)
        shares = []
        for i, mid in enumerate(body.shared_between):
            amt = base + (1 if i < extra else 0)
            s.add(Share(expense_id=e.id, group_id=gid, member_id=mid, amount=amt))
            shares.append({"member_id": mid, "amount": cedis(amt)})
        s.commit()
        return {"id": e.id, "paid_by": e.paid_by, "amount": cedis(total), "shares": shares}


@app.post("/groups/{gid}/payments", status_code=201)
def create_payment(gid: int, body: PaymentIn):
    with Session(engine) as s:
        get_group(s, gid)
        amt = to_pesewas(body.amount)
        check_member(s, gid, body.from_member)
        check_member(s, gid, body.to_member)
        if body.from_member == body.to_member:
            raise HTTPException(422, "Nobody can pay themselves back")
        p = Payment(group_id=gid, from_member=body.from_member, to_member=body.to_member, amount=amt)
        s.add(p)
        s.commit()
        return {"id": p.id, "from_member": p.from_member, "to_member": p.to_member, "amount": cedis(amt)}


@app.get("/groups/{gid}/balances")
def balances(gid: int):
    with Session(engine) as s:
        get_group(s, gid)
        ms = members_of(s, gid)
        bal = {m.id: 0 for m in ms}
        for e in s.exec(select(Expense).where(Expense.group_id == gid)).all():
            bal[e.paid_by] += e.amount
        for sh in s.exec(select(Share).where(Share.group_id == gid)).all():
            bal[sh.member_id] -= sh.amount
        for p in s.exec(select(Payment).where(Payment.group_id == gid)).all():
            bal[p.from_member] += p.amount
            bal[p.to_member] -= p.amount
        return [{"member_id": m.id, "name": m.name, "balance": cedis(bal[m.id])} for m in ms]
