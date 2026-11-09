from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import UniqueConstraint, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field as SQLField, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///susu.db", connect_args={"check_same_thread": False})


# ---------- Database tables ----------
class Group(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str


class Member(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="group.id", index=True)
    name: str
    phone: str


class Payment(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="group.id", index=True)
    member_id: int = SQLField(foreign_key="member.id", index=True)
    round: int
    amount_pesewas: int  # money kept as whole pesewas to avoid rounding errors


class Collection(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("group_id", "round", name="one_collector_per_round"),
        UniqueConstraint("group_id", "member_id", name="one_collection_per_member"),
    )
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="group.id", index=True)
    round: int
    member_id: int = SQLField(foreign_key="member.id")
    pot_pesewas: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Susu Group Records", lifespan=lifespan)


def get_session():
    with Session(engine) as session:
        yield session


# ---------- Request bodies ----------
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _not_blank(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("must not be empty")
    return v


class GroupIn(Strict):
    name: str = Field(max_length=200)
    _check = field_validator("name")(_not_blank)


class MemberIn(Strict):
    name: str = Field(max_length=200)
    phone: str = Field(max_length=50)
    _check = field_validator("name", "phone")(_not_blank)


class PaymentIn(Strict):
    member_id: int
    round: int = Field(ge=1)
    amount: Decimal = Field(gt=0, le=Decimal("1000000000"))

    @field_validator("amount")
    @classmethod
    def two_places(cls, v: Decimal) -> Decimal:
        if v != v.quantize(Decimal("0.01")):
            raise ValueError("amount can have at most 2 decimal places (pesewas)")
        return v


class CollectionIn(Strict):
    member_id: int
    round: int = Field(ge=1)


# ---------- Helpers ----------
def cedis(pesewas: int) -> float:
    return float(Decimal(pesewas) / 100)


def get_group(session: Session, group_id: int) -> Group:
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    return group


def get_member(session: Session, group_id: int, member_id: int) -> Member:
    member = session.get(Member, member_id)
    if not member or member.group_id != group_id:
        raise HTTPException(404, "Member not found in this group")
    return member


def member_out(m: Member) -> dict:
    return {"id": m.id, "group_id": m.group_id, "name": m.name, "phone": m.phone}


def collection_out(c: Collection, member_name: str) -> dict:
    return {
        "id": c.id,
        "group_id": c.group_id,
        "round": c.round,
        "member_id": c.member_id,
        "member_name": member_name,
        "pot": cedis(c.pot_pesewas),
    }


# ---------- Endpoints ----------
@app.post("/groups", status_code=201)
def create_group(body: GroupIn, session: Session = Depends(get_session)):
    group = Group(name=body.name)
    session.add(group)
    session.commit()
    session.refresh(group)
    return {"id": group.id, "name": group.name}


@app.post("/groups/{group_id}/members", status_code=201)
def add_member(group_id: int, body: MemberIn, session: Session = Depends(get_session)):
    get_group(session, group_id)
    member = Member(group_id=group_id, name=body.name, phone=body.phone)
    session.add(member)
    session.commit()
    session.refresh(member)
    return member_out(member)


@app.get("/groups/{group_id}/members")
def list_members(group_id: int, session: Session = Depends(get_session)):
    get_group(session, group_id)
    members = session.exec(
        select(Member).where(Member.group_id == group_id).order_by(Member.id)
    ).all()
    return [member_out(m) for m in members]


@app.post("/groups/{group_id}/payments", status_code=201)
def record_payment(group_id: int, body: PaymentIn, session: Session = Depends(get_session)):
    get_group(session, group_id)
    get_member(session, group_id, body.member_id)
    collected = session.exec(
        select(Collection).where(
            Collection.group_id == group_id, Collection.round == body.round
        )
    ).first()
    if collected:
        raise HTTPException(409, f"Round {body.round} has already been collected; no more payments allowed")
    payment = Payment(
        group_id=group_id,
        member_id=body.member_id,
        round=body.round,
        amount_pesewas=int(body.amount * 100),
    )
    session.add(payment)
    session.commit()
    session.refresh(payment)
    return {
        "id": payment.id,
        "group_id": payment.group_id,
        "member_id": payment.member_id,
        "round": payment.round,
        "amount": cedis(payment.amount_pesewas),
    }


@app.post("/groups/{group_id}/collections", status_code=201)
def record_collection(group_id: int, body: CollectionIn, session: Session = Depends(get_session)):
    get_group(session, group_id)
    member = get_member(session, group_id, body.member_id)
    if session.exec(
        select(Collection).where(Collection.group_id == group_id, Collection.round == body.round)
    ).first():
        raise HTTPException(409, f"Round {body.round} has already been collected")
    if session.exec(
        select(Collection).where(Collection.group_id == group_id, Collection.member_id == body.member_id)
    ).first():
        raise HTTPException(409, "This member has already collected")
    pot = session.exec(
        select(func.coalesce(func.sum(Payment.amount_pesewas), 0)).where(
            Payment.group_id == group_id, Payment.round == body.round
        )
    ).one()
    if not pot:
        raise HTTPException(409, f"Nobody has paid anything into round {body.round}; it cannot be collected")
    collection = Collection(group_id=group_id, round=body.round, member_id=body.member_id, pot_pesewas=pot)
    session.add(collection)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "This round or this member has already been collected")
    session.refresh(collection)
    return collection_out(collection, member.name)


@app.get("/groups/{group_id}/collections")
def list_collections(group_id: int, session: Session = Depends(get_session)):
    get_group(session, group_id)
    rows = session.exec(
        select(Collection, Member.name)
        .join(Member, Member.id == Collection.member_id)
        .where(Collection.group_id == group_id)
        .order_by(Collection.round)
    ).all()
    return [collection_out(c, name) for c, name in rows]


@app.get("/groups/{group_id}/members/{member_id}/statement")
def member_statement(group_id: int, member_id: int, session: Session = Depends(get_session)):
    get_group(session, group_id)
    member = get_member(session, group_id, member_id)
    paid = session.exec(
        select(func.coalesce(func.sum(Payment.amount_pesewas), 0)).where(
            Payment.group_id == group_id, Payment.member_id == member_id
        )
    ).one()
    received = session.exec(
        select(func.coalesce(func.sum(Collection.pot_pesewas), 0)).where(
            Collection.group_id == group_id, Collection.member_id == member_id
        )
    ).one()
    return {
        "member_id": member.id,
        "name": member.name,
        "phone": member.phone,
        "total_paid": cedis(paid),
        "total_received": cedis(received),
    }
