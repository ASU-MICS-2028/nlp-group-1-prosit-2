from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as F, Session, create_engine, select, func


class Group(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    name: str


class Member(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    group_id: int = F(index=True)
    name: str
    phone: str


class Contribution(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    group_id: int = F(index=True)
    member_id: int = F(index=True)
    round: int
    amount: float


class Collection(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    group_id: int = F(index=True)
    member_id: int = F(index=True)
    round: int
    amount: float


engine = create_engine("sqlite:///susu.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)
app = FastAPI()


class GroupIn(BaseModel):
    name: str = Field(min_length=1)


class MemberIn(BaseModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)


class ContributionIn(BaseModel):
    member_id: int
    round: int = Field(ge=1)
    amount: float = Field(gt=0)


class CollectionIn(BaseModel):
    member_id: int
    round: int = Field(ge=1)


def get_group(s, gid):
    g = s.get(Group, gid)
    if not g:
        raise HTTPException(404, "Group not found")
    return g


def get_member(s, gid, mid):
    m = s.get(Member, mid)
    if not m or m.group_id != gid:
        raise HTTPException(404, "Member not found in this group")
    return m


def total(s, model, **filters):
    q = select(func.coalesce(func.sum(model.amount), 0))
    for k, v in filters.items():
        q = q.where(getattr(model, k) == v)
    return float(s.exec(q).one())


@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    with Session(engine) as s:
        g = Group(name=body.name)
        s.add(g)
        s.commit()
        s.refresh(g)
        return g


@app.get("/groups/{gid}")
def read_group(gid: int):
    with Session(engine) as s:
        return get_group(s, gid)


@app.post("/groups/{gid}/members", status_code=201)
def add_member(gid: int, body: MemberIn):
    with Session(engine) as s:
        get_group(s, gid)
        m = Member(group_id=gid, name=body.name, phone=body.phone)
        s.add(m)
        s.commit()
        s.refresh(m)
        return m


@app.get("/groups/{gid}/members")
def list_members(gid: int):
    with Session(engine) as s:
        get_group(s, gid)
        return s.exec(select(Member).where(Member.group_id == gid)).all()


@app.post("/groups/{gid}/contributions", status_code=201)
def pay(gid: int, body: ContributionIn):
    with Session(engine) as s:
        get_group(s, gid)
        get_member(s, gid, body.member_id)
        if s.exec(select(Collection).where(Collection.group_id == gid, Collection.round == body.round)).first():
            raise HTTPException(409, "Round already collected")
        c = Contribution(group_id=gid, member_id=body.member_id, round=body.round, amount=body.amount)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


@app.post("/groups/{gid}/collections", status_code=201)
def collect(gid: int, body: CollectionIn):
    with Session(engine) as s:
        get_group(s, gid)
        get_member(s, gid, body.member_id)
        if s.exec(select(Collection).where(Collection.group_id == gid, Collection.round == body.round)).first():
            raise HTTPException(409, "Round already collected")
        if s.exec(select(Collection).where(Collection.group_id == gid, Collection.member_id == body.member_id)).first():
            raise HTTPException(409, "Member has already collected")
        pot = total(s, Contribution, group_id=gid, round=body.round)
        if pot <= 0:
            raise HTTPException(409, "Nothing paid in for this round")
        c = Collection(group_id=gid, member_id=body.member_id, round=body.round, amount=pot)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


@app.get("/groups/{gid}/collections")
def list_collections(gid: int):
    with Session(engine) as s:
        get_group(s, gid)
        return s.exec(select(Collection).where(Collection.group_id == gid).order_by(Collection.round)).all()


@app.get("/groups/{gid}/members/{mid}/statement")
def statement(gid: int, mid: int):
    with Session(engine) as s:
        get_group(s, gid)
        m = get_member(s, gid, mid)
        return {
            "member_id": m.id,
            "name": m.name,
            "total_paid": total(s, Contribution, member_id=mid),
            "total_received": total(s, Collection, member_id=mid),
        }
