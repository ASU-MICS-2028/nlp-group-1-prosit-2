import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Session, SQLModel, create_engine, select, func, Field as SQLField

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
    pesewas: int


class Collection(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("group_id", "round"),
        UniqueConstraint("group_id", "member_id"),
    )
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="group.id", index=True)
    member_id: int = SQLField(foreign_key="member.id")
    round: int
    pesewas: int


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Susu Group Records", lifespan=lifespan)


def cedis(pesewas: int) -> float:
    return round(pesewas / 100, 2)


class NameIn(BaseModel):
    name: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class MemberIn(BaseModel):
    name: str
    phone: str

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class ContributionIn(BaseModel):
    member_id: int
    round: int = Field(ge=1)
    amount: float

    @field_validator("amount")
    @classmethod
    def positive(cls, v):
        if not (v > 0) or v != v or v == float("inf"):
            raise ValueError("contribution must be more than zero")
        p = round(v * 100)
        if abs(v * 100 - p) > 1e-6:
            raise ValueError("amount can have at most 2 decimal places (pesewas)")
        if p <= 0:
            raise ValueError("contribution must be more than zero")
        return v


class CollectionIn(BaseModel):
    member_id: int
    round: int = Field(ge=1)


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


def member_out(m: Member):
    return {"id": m.id, "group_id": m.group_id, "name": m.name, "phone": m.phone}


def collection_out(c: Collection, s: Session):
    m = s.get(Member, c.member_id)
    return {"id": c.id, "group_id": c.group_id, "round": c.round, "member_id": c.member_id,
            "member_name": m.name if m else None, "amount": cedis(c.pesewas)}


@app.post("/groups", status_code=201)
def create_group(body: NameIn):
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
def pay(group_id: int, body: ContributionIn):
    with write_lock, Session(engine) as s:
        get_group(s, group_id)
        get_member(s, group_id, body.member_id)
        done = s.exec(select(Collection).where(Collection.group_id == group_id,
                                               Collection.round == body.round)).first()
        if done:
            raise HTTPException(409, f"Round {body.round} has already been collected; no more payments allowed")
        c = Contribution(group_id=group_id, member_id=body.member_id, round=body.round,
                         pesewas=round(body.amount * 100))
        s.add(c)
        s.commit()
        s.refresh(c)
        return {"id": c.id, "group_id": group_id, "member_id": c.member_id,
                "round": c.round, "amount": cedis(c.pesewas)}


@app.post("/groups/{group_id}/collections", status_code=201)
def collect(group_id: int, body: CollectionIn):
    with write_lock, Session(engine) as s:
        get_group(s, group_id)
        get_member(s, group_id, body.member_id)
        if s.exec(select(Collection).where(Collection.group_id == group_id,
                                           Collection.round == body.round)).first():
            raise HTTPException(409, f"Round {body.round} has already been collected")
        if s.exec(select(Collection).where(Collection.group_id == group_id,
                                           Collection.member_id == body.member_id)).first():
            raise HTTPException(409, "This member has already collected")
        total = s.exec(select(func.coalesce(func.sum(Contribution.pesewas), 0)).where(
            Contribution.group_id == group_id, Contribution.round == body.round)).one()
        if not total:
            raise HTTPException(409, f"Nobody has paid into round {body.round}; it cannot be collected")
        c = Collection(group_id=group_id, member_id=body.member_id, round=body.round, pesewas=total)
        s.add(c)
        s.commit()
        s.refresh(c)
        return collection_out(c, s)


@app.get("/groups/{group_id}/collections")
def list_collections(group_id: int):
    with Session(engine) as s:
        get_group(s, group_id)
        cs = s.exec(select(Collection).where(Collection.group_id == group_id).order_by(Collection.round)).all()
        return [collection_out(c, s) for c in cs]


@app.get("/groups/{group_id}/members/{member_id}/statement")
def statement(group_id: int, member_id: int):
    with Session(engine) as s:
        get_group(s, group_id)
        m = get_member(s, group_id, member_id)
        paid = s.exec(select(func.coalesce(func.sum(Contribution.pesewas), 0)).where(
            Contribution.member_id == member_id)).one()
        received = s.exec(select(func.coalesce(func.sum(Collection.pesewas), 0)).where(
            Collection.member_id == member_id)).one()
        return {"member_id": m.id, "name": m.name, "phone": m.phone,
                "total_paid": cedis(paid), "total_received": cedis(received)}
