from typing import Optional

from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./susu.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class SusuGroup(SQLModel, table=True):
    __tablename__ = "susu_group"
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str


class Member(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="susu_group.id", index=True)
    name: str
    phone: str


class Payment(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="susu_group.id", index=True)
    round_number: int
    member_id: int = SQLField(foreign_key="member.id")
    amount: float


class Collection(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    group_id: int = SQLField(foreign_key="susu_group.id", index=True)
    round_number: int
    member_id: int = SQLField(foreign_key="member.id")
    pot: float


class GroupIn(BaseModel):
    name: str = Field(min_length=1)


class MemberIn(BaseModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)


class PaymentIn(BaseModel):
    member_id: int
    amount: float = Field(gt=0)


class CollectIn(BaseModel):
    member_id: int


SQLModel.metadata.create_all(engine)

app = FastAPI(title="Susu Group Records")


def _get_group(session: Session, group_id: int) -> SusuGroup:
    group = session.get(SusuGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


def _get_member(session: Session, group_id: int, member_id: int) -> Member:
    member = session.get(Member, member_id)
    if member is None or member.group_id != group_id:
        raise HTTPException(status_code=404, detail="Member not found in this group")
    return member


def _round_collection(session: Session, group_id: int, round_number: int) -> Optional[Collection]:
    return session.exec(
        select(Collection).where(
            Collection.group_id == group_id, Collection.round_number == round_number
        )
    ).first()


def _round_total(session: Session, group_id: int, round_number: int) -> float:
    payments = session.exec(
        select(Payment).where(
            Payment.group_id == group_id, Payment.round_number == round_number
        )
    ).all()
    return round(sum(p.amount for p in payments), 2)


RoundPath = Path(ge=1, description="Round number, starting at 1")


@app.post("/groups", status_code=201)
def create_group(body: GroupIn):
    with Session(engine) as session:
        group = SusuGroup(name=body.name)
        session.add(group)
        session.commit()
        session.refresh(group)
        return {"id": group.id, "name": group.name}


@app.post("/groups/{group_id}/members", status_code=201)
def add_member(group_id: int, body: MemberIn):
    with Session(engine) as session:
        _get_group(session, group_id)
        member = Member(group_id=group_id, name=body.name, phone=body.phone)
        session.add(member)
        session.commit()
        session.refresh(member)
        return {
            "id": member.id,
            "group_id": group_id,
            "name": member.name,
            "phone": member.phone,
        }


@app.get("/groups/{group_id}/members")
def list_members(group_id: int):
    with Session(engine) as session:
        _get_group(session, group_id)
        members = session.exec(select(Member).where(Member.group_id == group_id)).all()
        return [
            {"id": m.id, "name": m.name, "phone": m.phone} for m in members
        ]


@app.post("/groups/{group_id}/rounds/{round_number}/payments", status_code=201)
def record_payment(group_id: int, body: PaymentIn, round_number: int = RoundPath):
    with Session(engine) as session:
        _get_group(session, group_id)
        _get_member(session, group_id, body.member_id)
        if _round_collection(session, group_id, round_number) is not None:
            raise HTTPException(
                status_code=409,
                detail="This round has already been collected; no more payments can be made into it",
            )
        payment = Payment(
            group_id=group_id,
            round_number=round_number,
            member_id=body.member_id,
            amount=body.amount,
        )
        session.add(payment)
        session.commit()
        session.refresh(payment)
        return {
            "id": payment.id,
            "group_id": group_id,
            "round_number": round_number,
            "member_id": payment.member_id,
            "amount": payment.amount,
        }


@app.post("/groups/{group_id}/rounds/{round_number}/collect", status_code=201)
def collect_round(group_id: int, body: CollectIn, round_number: int = RoundPath):
    with Session(engine) as session:
        _get_group(session, group_id)
        member = _get_member(session, group_id, body.member_id)
        if _round_collection(session, group_id, round_number) is not None:
            raise HTTPException(status_code=409, detail="This round has already been collected")
        already = session.exec(
            select(Collection).where(
                Collection.group_id == group_id, Collection.member_id == member.id
            )
        ).first()
        if already is not None:
            raise HTTPException(
                status_code=409,
                detail=f"{member.name} has already collected a pot and cannot collect again",
            )
        pot = _round_total(session, group_id, round_number)
        if pot <= 0:
            raise HTTPException(
                status_code=409,
                detail="Nobody has paid into this round, so it cannot be collected",
            )
        collection = Collection(
            group_id=group_id,
            round_number=round_number,
            member_id=member.id,
            pot=pot,
        )
        session.add(collection)
        session.commit()
        session.refresh(collection)
        return {
            "id": collection.id,
            "group_id": group_id,
            "round_number": round_number,
            "member_id": member.id,
            "member_name": member.name,
            "pot": collection.pot,
        }


@app.get("/groups/{group_id}/collections")
def list_collections(group_id: int):
    with Session(engine) as session:
        _get_group(session, group_id)
        collections = session.exec(
            select(Collection)
            .where(Collection.group_id == group_id)
            .order_by(Collection.round_number)
        ).all()
        result = []
        for c in collections:
            member = session.get(Member, c.member_id)
            result.append(
                {
                    "id": c.id,
                    "round_number": c.round_number,
                    "member_id": c.member_id,
                    "member_name": member.name if member else None,
                    "pot": c.pot,
                }
            )
        return result


@app.get("/groups/{group_id}/members/{member_id}/statement")
def member_statement(group_id: int, member_id: int):
    with Session(engine) as session:
        _get_group(session, group_id)
        member = _get_member(session, group_id, member_id)
        payments = session.exec(
            select(Payment).where(
                Payment.group_id == group_id, Payment.member_id == member_id
            )
        ).all()
        collections = session.exec(
            select(Collection).where(
                Collection.group_id == group_id, Collection.member_id == member_id
            )
        ).all()
        return {
            "member_id": member.id,
            "name": member.name,
            "phone": member.phone,
            "total_paid": round(sum(p.amount for p in payments), 2),
            "total_received": round(sum(c.pot for c in collections), 2),
        }
