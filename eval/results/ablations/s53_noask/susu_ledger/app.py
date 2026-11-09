import threading
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Session, SQLModel, Field as DBField, create_engine, select

engine = create_engine("sqlite:///susu.db", connect_args={"check_same_thread": False})
write_lock = threading.Lock()


class Group(SQLModel, table=True):
    id: Optional[int] = DBField(default=None, primary_key=True)
    name: str


class Member(SQLModel, table=True):
    id: Optional[int] = DBField(default=None, primary_key=True)
    group_id: int = DBField(foreign_key="group.id", index=True)
    name: str
    phone: str


class Contribution(SQLModel, table=True):
    id: Optional[int] = DBField(default=None, primary_key=True)
    group_id: int = DBField(foreign_key="group.id", index=True)
    member_id: int = DBField(foreign_key="member.id", index=True)
    round_number: int
    amount_pesewas: int


class Collection(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("group_id", "round_number"),
        UniqueConstraint("member_id"),
    )
    id: Optional[int] = DBField(default=None, primary_key=True)
    group_id: int = DBField(foreign_key="group.id", index=True)
    member_id: int = DBField(foreign_key="member.id")
    round_number: int
    amount_pesewas: int


app = FastAPI(title="Susu Group Records")


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


# ---------- input models ----------

class GroupIn(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class MemberIn(BaseModel):
    name: str
    phone: str

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class ContributionIn(BaseModel):
    member_id: int
    round_number: int = Field(ge=1)
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def positive_cedis(cls, v):
        if not v.is_finite() or v <= 0:
            raise ValueError("amount must be more than zero")
        if v != v.quantize(Decimal("0.01")):
            raise ValueError("amount can have at most 2 decimal places (pesewas)")
        return v


class CollectionIn(BaseModel):
    member_id: int
    round_number: int = Field(ge=1)


# ---------- helpers ----------

def cedis(pesewas: int) -> float:
    return round(pesewas / 100, 2)


def get_group(session, group_id) -> Group:
    g = session.get(Group, group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    return g


def get_member(session, group_id, member_id) -> Member:
    m = session.get(Member, member_id)
    if not m or m.group_id != group_id:
        raise HTTPException(404, "Member not found in this group")
    return m


def member_out(m: Member):
    return {"id": m.id, "group_id": m.group_id, "name": m.name, "phone": m.phone}


def collection_out(c: Collection, m: Member):
    return {
        "id": c.id,
        "group_id": c.group_id,
        "round_number": c.round_number,
        "member_id": c.member_id,
        "member_name": m.name,
        "amount": cedis(c.amount_pesewas),
    }


# ---------- endpoints ----------

@app.post("/groups", status_code=201)
def create_group(data: GroupIn):
    with Session(engine) as s:
        g = Group(name=data.name)
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
def add_member(group_id: int, data: MemberIn):
    with Session(engine) as s:
        get_group(s, group_id)
        m = Member(group_id=group_id, name=data.name, phone=data.phone)
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
def add_contribution(group_id: int, data: ContributionIn):
    with write_lock, Session(engine) as s:
        get_group(s, group_id)
        m = get_member(s, group_id, data.member_id)
        done = s.exec(select(Collection).where(
            Collection.group_id == group_id,
            Collection.round_number == data.round_number)).first()
        if done:
            raise HTTPException(409, f"Round {data.round_number} has already been collected; no more payments allowed")
        c = Contribution(group_id=group_id, member_id=m.id, round_number=data.round_number,
                         amount_pesewas=int(data.amount * 100))
        s.add(c)
        s.commit()
        s.refresh(c)
        return {"id": c.id, "group_id": group_id, "member_id": m.id, "member_name": m.name,
                "round_number": c.round_number, "amount": cedis(c.amount_pesewas)}


@app.post("/groups/{group_id}/collections", status_code=201)
def make_collection(group_id: int, data: CollectionIn):
    with write_lock, Session(engine) as s:
        get_group(s, group_id)
        m = get_member(s, group_id, data.member_id)
        if s.exec(select(Collection).where(
                Collection.group_id == group_id,
                Collection.round_number == data.round_number)).first():
            raise HTTPException(409, f"Round {data.round_number} already has a collector")
        if s.exec(select(Collection).where(Collection.member_id == m.id)).first():
            raise HTTPException(409, f"{m.name} has already collected and cannot collect again")
        payments = s.exec(select(Contribution).where(
            Contribution.group_id == group_id,
            Contribution.round_number == data.round_number)).all()
        if not payments:
            raise HTTPException(409, f"Nobody has paid into round {data.round_number}; it cannot be collected")
        pot = sum(p.amount_pesewas for p in payments)
        c = Collection(group_id=group_id, member_id=m.id, round_number=data.round_number, amount_pesewas=pot)
        s.add(c)
        s.commit()
        s.refresh(c)
        return collection_out(c, m)


@app.get("/groups/{group_id}/collections")
def list_collections(group_id: int):
    with Session(engine) as s:
        get_group(s, group_id)
        cs = s.exec(select(Collection).where(Collection.group_id == group_id)
                    .order_by(Collection.round_number)).all()
        return [collection_out(c, s.get(Member, c.member_id)) for c in cs]


@app.get("/groups/{group_id}/members/{member_id}/statement")
def statement(group_id: int, member_id: int):
    with Session(engine) as s:
        get_group(s, group_id)
        m = get_member(s, group_id, member_id)
        pays = s.exec(select(Contribution).where(Contribution.member_id == m.id)
                      .order_by(Contribution.round_number, Contribution.id)).all()
        cols = s.exec(select(Collection).where(Collection.member_id == m.id)).all()
        return {
            "member": member_out(m),
            "total_paid": cedis(sum(p.amount_pesewas for p in pays)),
            "total_received": cedis(sum(c.amount_pesewas for c in cols)),
            "payments": [{"round_number": p.round_number, "amount": cedis(p.amount_pesewas)} for p in pays],
            "collections": [{"round_number": c.round_number, "amount": cedis(c.amount_pesewas)} for c in cols],
        }
