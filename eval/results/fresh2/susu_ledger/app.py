from contextlib import asynccontextmanager
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Field as SQLField, Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./susu.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


# ---------- database tables ----------
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
    round_number: int = SQLField(index=True)
    amount_pesewas: int


class Collection(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="group.id", index=True)
    member_id: int = SQLField(foreign_key="member.id", index=True)
    round_number: int = SQLField(index=True)
    amount_pesewas: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Susu Group Records", lifespan=lifespan)


# ---------- request bodies ----------
def _not_blank(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("must not be empty")
    return v


class GroupIn(BaseModel):
    name: str

    _v = field_validator("name")(classmethod(lambda cls, v: _not_blank(v)))


class MemberIn(BaseModel):
    name: str
    phone: str

    _v = field_validator("name", "phone")(classmethod(lambda cls, v: _not_blank(v)))


class ContributionIn(BaseModel):
    member_id: int
    round: int = Field(ge=1)
    amount: Decimal = Field(gt=0, description="Amount in cedis")

    @field_validator("amount")
    @classmethod
    def two_decimals(cls, v: Decimal) -> Decimal:
        if v != v.quantize(Decimal("0.01")):
            raise ValueError("amount can have at most 2 decimal places (pesewas)")
        return v


class CollectionIn(BaseModel):
    member_id: int
    round: int = Field(ge=1)


# ---------- helpers ----------
def to_pesewas(cedis: Decimal) -> int:
    return int((cedis * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_cedis(pesewas: int) -> float:
    return pesewas / 100


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


def group_out(g: Group) -> dict:
    return {"id": g.id, "name": g.name}


def member_out(m: Member) -> dict:
    return {"id": m.id, "group_id": m.group_id, "name": m.name, "phone": m.phone}


def contribution_out(c: Contribution) -> dict:
    return {
        "id": c.id,
        "group_id": c.group_id,
        "member_id": c.member_id,
        "round": c.round_number,
        "amount": to_cedis(c.amount_pesewas),
    }


def collection_out(c: Collection, member: Member) -> dict:
    return {
        "id": c.id,
        "group_id": c.group_id,
        "round": c.round_number,
        "member_id": c.member_id,
        "member_name": member.name,
        "amount": to_cedis(c.amount_pesewas),
    }


def round_collection(session: Session, group_id: int, round_number: int):
    return session.exec(
        select(Collection).where(
            Collection.group_id == group_id, Collection.round_number == round_number
        )
    ).first()


# ---------- endpoints ----------
@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    with Session(engine) as session:
        g = Group(name=body.name)
        session.add(g)
        session.commit()
        session.refresh(g)
        return group_out(g)


@app.get("/groups/{group_id}")
def read_group(group_id: int):
    with Session(engine) as session:
        return group_out(get_group(session, group_id))


@app.post("/groups/{group_id}/members", status_code=201)
def add_member(group_id: int, body: MemberIn):
    with Session(engine) as session:
        get_group(session, group_id)
        m = Member(group_id=group_id, name=body.name, phone=body.phone)
        session.add(m)
        session.commit()
        session.refresh(m)
        return member_out(m)


@app.get("/groups/{group_id}/members")
def list_members(group_id: int):
    with Session(engine) as session:
        get_group(session, group_id)
        members = session.exec(
            select(Member).where(Member.group_id == group_id).order_by(Member.id)
        ).all()
        return [member_out(m) for m in members]


@app.post("/groups/{group_id}/contributions", status_code=201)
def record_contribution(group_id: int, body: ContributionIn):
    with Session(engine) as session:
        get_group(session, group_id)
        get_member(session, group_id, body.member_id)
        if round_collection(session, group_id, body.round):
            raise HTTPException(
                409, f"Round {body.round} has already been collected; no more payments allowed"
            )
        c = Contribution(
            group_id=group_id,
            member_id=body.member_id,
            round_number=body.round,
            amount_pesewas=to_pesewas(body.amount),
        )
        session.add(c)
        session.commit()
        session.refresh(c)
        return contribution_out(c)


@app.post("/groups/{group_id}/collections", status_code=201)
def record_collection(group_id: int, body: CollectionIn):
    with Session(engine) as session:
        get_group(session, group_id)
        member = get_member(session, group_id, body.member_id)
        if round_collection(session, group_id, body.round):
            raise HTTPException(409, f"Round {body.round} has already been collected")
        already = session.exec(
            select(Collection).where(
                Collection.group_id == group_id, Collection.member_id == body.member_id
            )
        ).first()
        if already:
            raise HTTPException(
                409, f"This member already collected in round {already.round_number}"
            )
        payments = session.exec(
            select(Contribution).where(
                Contribution.group_id == group_id,
                Contribution.round_number == body.round,
            )
        ).all()
        pot = sum(p.amount_pesewas for p in payments)
        if pot <= 0:
            raise HTTPException(409, f"Nobody has paid into round {body.round} yet")
        c = Collection(
            group_id=group_id,
            member_id=body.member_id,
            round_number=body.round,
            amount_pesewas=pot,
        )
        session.add(c)
        session.commit()
        session.refresh(c)
        return collection_out(c, member)


@app.get("/groups/{group_id}/collections")
def list_collections(group_id: int):
    with Session(engine) as session:
        get_group(session, group_id)
        cols = session.exec(
            select(Collection)
            .where(Collection.group_id == group_id)
            .order_by(Collection.round_number)
        ).all()
        return [collection_out(c, session.get(Member, c.member_id)) for c in cols]


@app.get("/groups/{group_id}/members/{member_id}/statement")
def member_statement(group_id: int, member_id: int):
    with Session(engine) as session:
        get_group(session, group_id)
        member = get_member(session, group_id, member_id)
        paid = session.exec(
            select(Contribution)
            .where(Contribution.group_id == group_id, Contribution.member_id == member_id)
            .order_by(Contribution.id)
        ).all()
        received = session.exec(
            select(Collection).where(
                Collection.group_id == group_id, Collection.member_id == member_id
            )
        ).all()
        return {
            "member": member_out(member),
            "total_paid": to_cedis(sum(p.amount_pesewas for p in paid)),
            "total_received": to_cedis(sum(r.amount_pesewas for r in received)),
            "payments": [contribution_out(p) for p in paid],
            "collections": [collection_out(r, member) for r in received],
        }
