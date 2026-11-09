from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Field as F, Session, SQLModel, create_engine, select, func

engine = create_engine("sqlite:///susu.db", connect_args={"check_same_thread": False})


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
    member_id: int
    round: int
    amount: float


class Collection(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    group_id: int = F(index=True)
    round: int
    member_id: int
    amount: float


class GroupIn(BaseModel):
    name: str = Field(min_length=1)


class MemberIn(BaseModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)


class ContributionIn(BaseModel):
    member_id: int
    round: int = Field(ge=1)
    amount: float = Field(gt=0)


class CollectIn(BaseModel):
    member_id: int


SQLModel.metadata.create_all(engine)
app = FastAPI()


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


@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    with Session(engine) as s:
        g = Group(name=body.name)
        s.add(g)
        s.commit()
        s.refresh(g)
        return g


@app.get("/groups")
def list_groups():
    with Session(engine) as s:
        return s.exec(select(Group)).all()


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
        done = s.exec(select(Collection).where(
            Collection.group_id == gid, Collection.round == body.round)).first()
        if done:
            raise HTTPException(409, "This round has already been collected")
        c = Contribution(group_id=gid, member_id=body.member_id,
                         round=body.round, amount=body.amount)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


@app.post("/groups/{gid}/rounds/{rnd}/collect", status_code=201)
def collect(gid: int, rnd: int, body: CollectIn):
    with Session(engine) as s:
        get_group(s, gid)
        get_member(s, gid, body.member_id)
        if s.exec(select(Collection).where(
                Collection.group_id == gid, Collection.round == rnd)).first():
            raise HTTPException(409, "This round has already been collected")
        if s.exec(select(Collection).where(
                Collection.group_id == gid,
                Collection.member_id == body.member_id)).first():
            raise HTTPException(409, "This member has already collected")
        pot = s.exec(select(func.coalesce(func.sum(Contribution.amount), 0)).where(
            Contribution.group_id == gid, Contribution.round == rnd)).one()
        if not pot or pot <= 0:
            raise HTTPException(400, "Nobody has paid into this round")
        c = Collection(group_id=gid, round=rnd, member_id=body.member_id, amount=pot)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


@app.get("/groups/{gid}/collections")
def list_collections(gid: int):
    with Session(engine) as s:
        get_group(s, gid)
        return s.exec(select(Collection).where(Collection.group_id == gid)
                      .order_by(Collection.round)).all()


@app.get("/groups/{gid}/members/{mid}/statement")
def statement(gid: int, mid: int):
    with Session(engine) as s:
        get_group(s, gid)
        m = get_member(s, gid, mid)
        paid = s.exec(select(func.coalesce(func.sum(Contribution.amount), 0)).where(
            Contribution.group_id == gid, Contribution.member_id == mid)).one()
        got = s.exec(select(func.coalesce(func.sum(Collection.amount), 0)).where(
            Collection.group_id == gid, Collection.member_id == mid)).one()
        return {"member_id": m.id, "name": m.name, "phone": m.phone,
                "total_paid": paid, "total_received": got}
