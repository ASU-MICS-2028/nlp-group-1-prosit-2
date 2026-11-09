import threading
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel, Field as PField, StrictInt, field_validator
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, create_engine, select, func

engine = create_engine("sqlite:///susu.db", connect_args={"check_same_thread": False})
write_lock = threading.Lock()


# ---------- tables ----------
class Group(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class Member(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    name: str
    phone: str


class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    member_id: int = Field(foreign_key="member.id", index=True)
    round_number: int
    amount_pesewas: int


class Collection(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("group_id", "round_number"),
        UniqueConstraint("member_id"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    member_id: int = Field(foreign_key="member.id")
    round_number: int
    pot_pesewas: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Susu Group Records", lifespan=lifespan)


# ---------- request bodies ----------
def _clean_text(v):
    if not isinstance(v, str):
        raise ValueError("must be text")
    v = v.strip()
    if not v:
        raise ValueError("must not be empty")
    return v


class GroupIn(BaseModel):
    name: str = PField(max_length=200)

    _c = field_validator("name", mode="before")(_clean_text)


class MemberIn(BaseModel):
    name: str = PField(max_length=200)
    phone: str = PField(max_length=30)

    _c = field_validator("name", "phone", mode="before")(_clean_text)


class PaymentIn(BaseModel):
    member_id: StrictInt
    round_number: StrictInt = PField(ge=1, le=1_000_000)
    amount: Decimal = PField(gt=0, max_digits=12, decimal_places=2)

    @field_validator("amount", mode="before")
    @classmethod
    def no_bool(cls, v):
        if isinstance(v, bool):
            raise ValueError("amount must be a number")
        return v


class CollectionIn(BaseModel):
    member_id: StrictInt


# ---------- helpers ----------
def cedis(pesewas: int) -> float:
    return round(pesewas / 100, 2)


def get_group(s: Session, group_id: int) -> Group:
    g = s.get(Group, group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    return g


def get_member(s: Session, group_id: int, member_id: int, status: int = 404) -> Member:
    m = s.get(Member, member_id)
    if not m or m.group_id != group_id:
        raise HTTPException(status, "This person is not a member of this group")
    return m


def member_out(m: Member):
    return {"id": m.id, "group_id": m.group_id, "name": m.name, "phone": m.phone}


def collection_out(c: Collection, m: Member):
    return {
        "id": c.id,
        "round_number": c.round_number,
        "member_id": c.member_id,
        "member_name": m.name,
        "pot": cedis(c.pot_pesewas),
    }


# ---------- endpoints ----------
@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    with Session(engine) as s:
        g = Group(name=body.name)
        s.add(g)
        s.commit()
        s.refresh(g)
        return {"id": g.id, "name": g.name}


@app.post("/groups/{groupId}/members", status_code=201)
def add_member(body: MemberIn, groupId: int):
    with Session(engine) as s:
        get_group(s, groupId)
        m = Member(group_id=groupId, name=body.name, phone=body.phone)
        s.add(m)
        s.commit()
        s.refresh(m)
        return member_out(m)


@app.get("/groups/{groupId}/members")
def list_members(groupId: int):
    with Session(engine) as s:
        get_group(s, groupId)
        ms = s.exec(select(Member).where(Member.group_id == groupId).order_by(Member.id)).all()
        return [member_out(m) for m in ms]


@app.post("/groups/{groupId}/payments", status_code=201)
def record_payment(body: PaymentIn, groupId: int):
    with write_lock, Session(engine) as s:
        get_group(s, groupId)
        m = get_member(s, groupId, body.member_id, status=400)
        done = s.exec(
            select(Collection).where(
                Collection.group_id == groupId, Collection.round_number == body.round_number
            )
        ).first()
        if done:
            raise HTTPException(409, "This round has already been collected; no more payments allowed")
        p = Payment(
            group_id=groupId,
            member_id=m.id,
            round_number=body.round_number,
            amount_pesewas=int(body.amount * 100),
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        return {
            "id": p.id,
            "member_id": p.member_id,
            "member_name": m.name,
            "round_number": p.round_number,
            "amount": cedis(p.amount_pesewas),
        }


@app.post("/groups/{groupId}/rounds/{roundNumber}/collection", status_code=201)
def record_collection(body: CollectionIn, groupId: int, roundNumber: int = Path(ge=1, le=1_000_000)):
    with write_lock, Session(engine) as s:
        get_group(s, groupId)
        m = get_member(s, groupId, body.member_id, status=400)
        existing = s.exec(
            select(Collection).where(
                Collection.group_id == groupId, Collection.round_number == roundNumber
            )
        ).first()
        if existing:
            raise HTTPException(409, "This round already has a collector")
        if s.exec(select(Collection).where(Collection.member_id == m.id)).first():
            raise HTTPException(409, "This member has already collected before")
        pot = s.exec(
            select(func.coalesce(func.sum(Payment.amount_pesewas), 0)).where(
                Payment.group_id == groupId, Payment.round_number == roundNumber
            )
        ).one()
        if not pot:
            raise HTTPException(409, "Nobody has paid into this round, so it cannot be collected")
        c = Collection(group_id=groupId, member_id=m.id, round_number=roundNumber, pot_pesewas=pot)
        s.add(c)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            raise HTTPException(409, "This round or member has already been collected")
        s.refresh(c)
        return collection_out(c, m)


@app.get("/groups/{groupId}/collections")
def list_collections(groupId: int):
    with Session(engine) as s:
        get_group(s, groupId)
        rows = s.exec(
            select(Collection, Member)
            .where(Collection.group_id == groupId, Collection.member_id == Member.id)
            .order_by(Collection.round_number)
        ).all()
        return [collection_out(c, m) for c, m in rows]


@app.get("/groups/{groupId}/members/{memberId}/statement")
def statement(groupId: int, memberId: int):
    with Session(engine) as s:
        get_group(s, groupId)
        m = get_member(s, groupId, memberId)
        paid = s.exec(
            select(func.coalesce(func.sum(Payment.amount_pesewas), 0)).where(Payment.member_id == m.id)
        ).one()
        received = s.exec(
            select(func.coalesce(func.sum(Collection.pot_pesewas), 0)).where(Collection.member_id == m.id)
        ).one()
        return {
            "member_id": m.id,
            "name": m.name,
            "phone": m.phone,
            "total_paid": cedis(paid),
            "total_received": cedis(received),
        }
