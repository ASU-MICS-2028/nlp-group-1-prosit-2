import threading
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Session, SQLModel, create_engine, func, select

engine = create_engine("sqlite:///susu.db", connect_args={"check_same_thread": False})
write_lock = threading.Lock()


class Group(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


class Member(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    name: str
    phone: str


class Contribution(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    member_id: int = Field(foreign_key="member.id", index=True)
    round_number: int
    amount: int  # pesewas


class Collection(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("group_id", "round_number"),
        UniqueConstraint("group_id", "member_id"),
    )
    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    member_id: int = Field(foreign_key="member.id")
    round_number: int
    amount: int  # pesewas


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Susu group records", lifespan=lifespan)


def cedis(pesewas: int) -> float:
    return pesewas / 100


def pesewas(amount: Decimal) -> int:
    return int(amount * 100)


class GroupIn(BaseModel):
    name: str = PField(min_length=1)


class MemberIn(BaseModel):
    name: str = PField(min_length=1)
    phone: str = PField(min_length=1)


class ContributionIn(BaseModel):
    member_id: int
    round_number: int = PField(ge=1)
    amount: Decimal = PField(gt=0, decimal_places=2)


class CollectionIn(BaseModel):
    member_id: int
    round_number: int = PField(ge=1)


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
    return {"id": c.id, "group_id": c.group_id, "round_number": c.round_number,
            "member_id": c.member_id, "member_name": m.name, "amount": cedis(c.amount)}


def round_total(s: Session, group_id: int, round_number: int) -> int:
    return s.exec(select(func.coalesce(func.sum(Contribution.amount), 0)).where(
        Contribution.group_id == group_id, Contribution.round_number == round_number)).one()


@app.post("/groups", status_code=201)
def create_group(body: GroupIn) -> dict:
    with Session(engine) as s:
        if not body.name.strip():
            raise HTTPException(422, "Name cannot be blank")
        g = Group(name=body.name.strip())
        s.add(g)
        s.commit()
        s.refresh(g)
        return {"id": g.id, "name": g.name}


@app.get("/groups/{group_id}")
def show_group(group_id: int) -> dict:
    with Session(engine) as s:
        g = get_group(s, group_id)
        return {"id": g.id, "name": g.name}


@app.post("/groups/{group_id}/members", status_code=201)
def add_member(group_id: int, body: MemberIn) -> dict:
    if not body.name.strip() or not body.phone.strip():
        raise HTTPException(422, "Name and phone cannot be blank")
    with Session(engine) as s:
        get_group(s, group_id)
        m = Member(group_id=group_id, name=body.name.strip(), phone=body.phone.strip())
        s.add(m)
        s.commit()
        s.refresh(m)
        return member_out(m)


@app.get("/groups/{group_id}/members")
def list_members(group_id: int) -> list[dict]:
    with Session(engine) as s:
        get_group(s, group_id)
        ms = s.exec(select(Member).where(Member.group_id == group_id).order_by(Member.id)).all()
        return [member_out(m) for m in ms]


@app.post("/groups/{group_id}/contributions", status_code=201)
def pay_in(group_id: int, body: ContributionIn) -> dict:
    with write_lock, Session(engine) as s:
        get_group(s, group_id)
        get_member(s, group_id, body.member_id)
        done = s.exec(select(Collection).where(Collection.group_id == group_id,
                                               Collection.round_number == body.round_number)).first()
        if done:
            raise HTTPException(409, f"Round {body.round_number} has already been collected")
        c = Contribution(group_id=group_id, member_id=body.member_id,
                         round_number=body.round_number, amount=pesewas(body.amount))
        s.add(c)
        s.commit()
        s.refresh(c)
        return {"id": c.id, "group_id": group_id, "member_id": c.member_id,
                "round_number": c.round_number, "amount": cedis(c.amount),
                "round_total": cedis(round_total(s, group_id, c.round_number))}


@app.post("/groups/{group_id}/collections", status_code=201)
def collect(group_id: int, body: CollectionIn) -> dict:
    with write_lock, Session(engine) as s:
        get_group(s, group_id)
        m = get_member(s, group_id, body.member_id)
        if s.exec(select(Collection).where(Collection.group_id == group_id,
                                           Collection.round_number == body.round_number)).first():
            raise HTTPException(409, f"Round {body.round_number} has already been collected")
        if s.exec(select(Collection).where(Collection.group_id == group_id,
                                           Collection.member_id == body.member_id)).first():
            raise HTTPException(409, f"{m.name} has already collected")
        pot = round_total(s, group_id, body.round_number)
        if pot <= 0:
            raise HTTPException(409, f"Nobody has paid into round {body.round_number}")
        c = Collection(group_id=group_id, member_id=m.id, round_number=body.round_number, amount=pot)
        s.add(c)
        s.commit()
        s.refresh(c)
        return collection_out(c, m)


@app.get("/groups/{group_id}/collections")
def list_collections(group_id: int) -> list[dict]:
    with Session(engine) as s:
        get_group(s, group_id)
        rows = s.exec(select(Collection, Member).where(Collection.group_id == group_id,
                                                       Collection.member_id == Member.id)
                      .order_by(Collection.round_number)).all()
        return [collection_out(c, m) for c, m in rows]


@app.get("/groups/{group_id}/members/{member_id}/statement")
def statement(group_id: int, member_id: int) -> dict:
    with Session(engine) as s:
        get_group(s, group_id)
        m = get_member(s, group_id, member_id)
        paid = s.exec(select(func.coalesce(func.sum(Contribution.amount), 0)).where(
            Contribution.member_id == member_id)).one()
        received = s.exec(select(func.coalesce(func.sum(Collection.amount), 0)).where(
            Collection.member_id == member_id)).one()
        return {"member_id": m.id, "name": m.name, "phone": m.phone,
                "total_paid": cedis(paid), "total_received": cedis(received)}
