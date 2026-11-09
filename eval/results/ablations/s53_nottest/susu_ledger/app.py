import threading
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Field as SQLField, Session, SQLModel, create_engine, select, func

engine = create_engine("sqlite:///susu.db", connect_args={"check_same_thread": False})
write_lock = threading.Lock()


class Group(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str


class Member(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="group.id", index=True)
    name: str
    phone: str


class Contribution(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="group.id", index=True)
    member_id: int = SQLField(foreign_key="member.id", index=True)
    round: int
    amount_pesewas: int


class Collection(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("group_id", "round"),
        UniqueConstraint("group_id", "member_id"),
    )
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="group.id", index=True)
    member_id: int = SQLField(foreign_key="member.id")
    round: int
    amount_pesewas: int


app = FastAPI(title="Susu Group Records")


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


# ---------- request bodies ----------

def _clean(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("must not be empty")
    return v


class GroupIn(BaseModel):
    name: str

    _c = field_validator("name")(lambda cls, v: _clean(v))


class MemberIn(BaseModel):
    name: str
    phone: str

    _c = field_validator("name", "phone")(lambda cls, v: _clean(v))


class ContributionIn(BaseModel):
    member_id: int
    round: int = Field(ge=1)
    amount: Decimal = Field(gt=0, description="Amount in cedis, up to 2 decimal places")

    @field_validator("amount")
    @classmethod
    def two_places(cls, v: Decimal) -> Decimal:
        if v != v.quantize(Decimal("0.01")):
            raise ValueError("amount can have at most 2 decimal places (pesewas)")
        return v


class CollectionIn(BaseModel):
    member_id: int
    round: int = Field(ge=1)


# ---------- helpers ----------

def cedis(pesewas: int) -> float:
    return round(pesewas / 100, 2)


def get_group(s: Session, group_id: int) -> Group:
    g = s.get(Group, group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    return g


def get_member(s: Session, group_id: int, member_id: int) -> Member:
    m = s.get(Member, member_id)
    if not m or m.group_id != group_id:
        raise HTTPException(404, "Member not found in this group")
    return m


def member_out(m: Member) -> dict:
    return {"id": m.id, "group_id": m.group_id, "name": m.name, "phone": m.phone}


def collection_out(c: Collection, m: Member) -> dict:
    return {
        "id": c.id,
        "round": c.round,
        "member_id": c.member_id,
        "member_name": m.name,
        "amount": cedis(c.amount_pesewas),
    }


# ---------- endpoints ----------

@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    with write_lock, Session(engine) as s:
        g = Group(name=body.name)
        s.add(g)
        s.commit()
        s.refresh(g)
        return {"id": g.id, "name": g.name}


@app.get("/groups/{group_id}")
def read_group(group_id: int):
    with Session(engine) as s:
        g = get_group(s, group_id)
        return {"id": g.id, "name": g.name}


@app.post("/groups/{group_id}/members", status_code=201)
def add_member(group_id: int, body: MemberIn):
    with write_lock, Session(engine) as s:
        get_group(s, group_id)
        m = Member(group_id=group_id, name=body.name, phone=body.phone)
        s.add(m)
        s.commit()
        s.refresh(m)
        return member_out(m)


@app.get("/groups/{group_id}/members")
def list_members(group_id: int):
    with Session(engine) as s:
        get_group(s, group_id)
        ms = s.exec(select(Member).where(Member.group_id == group_id).order_by(Member.id)).all()
        return [member_out(m) for m in ms]


@app.post("/groups/{group_id}/contributions", status_code=201)
def add_contribution(group_id: int, body: ContributionIn):
    with write_lock, Session(engine) as s:
        get_group(s, group_id)
        m = get_member(s, group_id, body.member_id)
        collected = s.exec(
            select(Collection).where(Collection.group_id == group_id, Collection.round == body.round)
        ).first()
        if collected:
            raise HTTPException(409, f"Round {body.round} has already been collected; no more payments allowed")
        c = Contribution(
            group_id=group_id,
            member_id=m.id,
            round=body.round,
            amount_pesewas=int(body.amount * 100),
        )
        s.add(c)
        s.commit()
        s.refresh(c)
        return {
            "id": c.id,
            "member_id": c.member_id,
            "member_name": m.name,
            "round": c.round,
            "amount": cedis(c.amount_pesewas),
        }


@app.post("/groups/{group_id}/collections", status_code=201)
def collect(group_id: int, body: CollectionIn):
    with write_lock, Session(engine) as s:
        get_group(s, group_id)
        m = get_member(s, group_id, body.member_id)
        if s.exec(select(Collection).where(Collection.group_id == group_id, Collection.round == body.round)).first():
            raise HTTPException(409, f"Round {body.round} has already been collected")
        if s.exec(select(Collection).where(Collection.group_id == group_id, Collection.member_id == m.id)).first():
            raise HTTPException(409, f"{m.name} has already collected and cannot collect again")
        pot = s.exec(
            select(func.coalesce(func.sum(Contribution.amount_pesewas), 0)).where(
                Contribution.group_id == group_id, Contribution.round == body.round
            )
        ).one()
        if not pot:
            raise HTTPException(409, f"Nobody has paid into round {body.round}; it cannot be collected")
        c = Collection(group_id=group_id, member_id=m.id, round=body.round, amount_pesewas=pot)
        s.add(c)
        s.commit()
        s.refresh(c)
        return collection_out(c, m)


@app.get("/groups/{group_id}/collections")
def list_collections(group_id: int):
    with Session(engine) as s:
        get_group(s, group_id)
        rows = s.exec(
            select(Collection, Member)
            .where(Collection.group_id == group_id, Collection.member_id == Member.id)
            .order_by(Collection.round)
        ).all()
        return [collection_out(c, m) for c, m in rows]


@app.get("/groups/{group_id}/members/{member_id}/statement")
def statement(group_id: int, member_id: int):
    with Session(engine) as s:
        get_group(s, group_id)
        m = get_member(s, group_id, member_id)
        paid = s.exec(
            select(func.coalesce(func.sum(Contribution.amount_pesewas), 0)).where(Contribution.member_id == m.id)
        ).one()
        received = s.exec(
            select(func.coalesce(func.sum(Collection.amount_pesewas), 0)).where(Collection.member_id == m.id)
        ).one()
        return {
            "member_id": m.id,
            "name": m.name,
            "phone": m.phone,
            "total_paid": cedis(paid),
            "total_received": cedis(received),
        }
