from decimal import Decimal
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, create_engine, select

engine = create_engine(
    "sqlite:///./expenses.db", connect_args={"check_same_thread": False}
)


# ---------- stored tables ----------

class Group(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str


class Member(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="group.id", index=True)
    name: str


class Expense(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="group.id", index=True)
    payer: str
    amount_pesewas: int


class ExpenseShare(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="group.id", index=True)
    expense_id: int = SQLField(foreign_key="expense.id", index=True)
    member: str
    share_pesewas: int


class Payment(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="group.id", index=True)
    paid_by: str
    paid_to: str
    amount_pesewas: int


SQLModel.metadata.create_all(engine)

app = FastAPI(title="Shared costs tracker")


# ---------- request models ----------

class GroupCreate(BaseModel):
    name: str
    members: List[str]

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class ExpenseCreate(BaseModel):
    payer: str
    amount: Decimal
    shared_between: List[str]


class PaymentCreate(BaseModel):
    paid_by: str
    paid_to: str
    amount: Decimal


# ---------- helpers ----------

def clean_name(value: str, what: str = "name") -> str:
    value = value.strip()
    if not value:
        raise HTTPException(status_code=400, detail=f"{what} must not be empty")
    return value


def amount_to_pesewas(amount: Decimal) -> int:
    if not amount.is_finite() or amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be more than zero")
    pesewas = amount * 100
    if pesewas != pesewas.to_integral_value():
        raise HTTPException(
            status_code=400, detail="amount can have at most two decimal places (pesewas)"
        )
    return int(pesewas)


def split_equally(total: int, count: int) -> List[int]:
    """Split total pesewas into `count` shares that differ by at most 1 and sum to total."""
    base, extra = divmod(total, count)
    return [base + 1] * extra + [base] * (count - extra)


def get_group_or_404(session: Session, group_id: int) -> Group:
    group = session.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    return group


def member_names(session: Session, group_id: int) -> List[str]:
    rows = session.exec(
        select(Member).where(Member.group_id == group_id).order_by(Member.id)
    ).all()
    return [r.name for r in rows]


def require_member(session: Session, group_id: int, name: str, members: List[str]) -> None:
    if name not in members:
        raise HTTPException(status_code=400, detail=f"'{name}' is not a member of this group")


def group_view(session: Session, group: Group) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "members": member_names(session, group.id),
    }


# ---------- endpoints ----------

@app.post("/groups", status_code=201)
def create_group(body: GroupCreate):
    members = [clean_name(m, "member name") for m in body.members]
    if not members:
        raise HTTPException(status_code=400, detail="a group needs at least one member")
    if len(set(members)) != len(members):
        raise HTTPException(status_code=400, detail="member names must be unique")
    with Session(engine) as session:
        group = Group(name=body.name)
        session.add(group)
        session.commit()
        session.refresh(group)
        for name in members:
            session.add(Member(group_id=group.id, name=name))
        session.commit()
        return group_view(session, group)


@app.get("/groups/{group_id}")
def get_group(group_id: int):
    with Session(engine) as session:
        group = get_group_or_404(session, group_id)
        return group_view(session, group)


@app.post("/groups/{group_id}/expenses", status_code=201)
def add_expense(group_id: int, body: ExpenseCreate):
    total = amount_to_pesewas(body.amount)
    with Session(engine) as session:
        get_group_or_404(session, group_id)
        members = member_names(session, group_id)
        payer = clean_name(body.payer, "payer")
        require_member(session, group_id, payer, members)

        sharers = [clean_name(s, "shared_between name") for s in body.shared_between]
        if not sharers:
            raise HTTPException(status_code=400, detail="shared_between must not be empty")
        if len(set(sharers)) != len(sharers):
            raise HTTPException(status_code=400, detail="shared_between names must be unique")
        for s in sharers:
            require_member(session, group_id, s, members)

        expense = Expense(group_id=group_id, payer=payer, amount_pesewas=total)
        session.add(expense)
        session.commit()
        session.refresh(expense)

        shares = split_equally(total, len(sharers))
        for name, share in zip(sharers, shares):
            session.add(
                ExpenseShare(
                    group_id=group_id,
                    expense_id=expense.id,
                    member=name,
                    share_pesewas=share,
                )
            )
        session.commit()

        return {
            "id": expense.id,
            "group_id": group_id,
            "payer": payer,
            "amount": total / 100,
            "shares": [
                {"member": n, "share": s / 100} for n, s in zip(sharers, shares)
            ],
        }


@app.post("/groups/{group_id}/payments", status_code=201)
def add_payment(group_id: int, body: PaymentCreate):
    total = amount_to_pesewas(body.amount)
    with Session(engine) as session:
        get_group_or_404(session, group_id)
        members = member_names(session, group_id)
        paid_by = clean_name(body.paid_by, "paid_by")
        paid_to = clean_name(body.paid_to, "paid_to")
        require_member(session, group_id, paid_by, members)
        require_member(session, group_id, paid_to, members)
        if paid_by == paid_to:
            raise HTTPException(status_code=400, detail="nobody can pay themselves back")

        payment = Payment(
            group_id=group_id, paid_by=paid_by, paid_to=paid_to, amount_pesewas=total
        )
        session.add(payment)
        session.commit()
        session.refresh(payment)
        return {
            "id": payment.id,
            "group_id": group_id,
            "paid_by": paid_by,
            "paid_to": paid_to,
            "amount": total / 100,
        }


@app.get("/groups/{group_id}/balances")
def get_balances(group_id: int):
    with Session(engine) as session:
        get_group_or_404(session, group_id)
        members = member_names(session, group_id)
        balances = {m: 0 for m in members}

        expenses = session.exec(select(Expense).where(Expense.group_id == group_id)).all()
        for e in expenses:
            balances[e.payer] = balances.get(e.payer, 0) + e.amount_pesewas

        shares = session.exec(
            select(ExpenseShare).where(ExpenseShare.group_id == group_id)
        ).all()
        for s in shares:
            balances[s.member] = balances.get(s.member, 0) - s.share_pesewas

        payments = session.exec(select(Payment).where(Payment.group_id == group_id)).all()
        for p in payments:
            balances[p.paid_by] = balances.get(p.paid_by, 0) + p.amount_pesewas
            balances[p.paid_to] = balances.get(p.paid_to, 0) - p.amount_pesewas

        return {
            "group_id": group_id,
            "balances": [
                {"member": m, "balance": balances[m] / 100} for m in members
            ],
            "total": sum(balances.values()) / 100,
        }
