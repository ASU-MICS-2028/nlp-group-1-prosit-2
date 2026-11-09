from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import event, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./wallets.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30})


# Make SQLite transactions take the write lock up front so concurrent
# transfers cannot interleave (no lost updates, no negative balances).
@event.listens_for(engine, "connect")
def _connect(dbapi_conn, _):
    dbapi_conn.isolation_level = None


@event.listens_for(engine, "begin")
def _begin(conn):
    conn.exec_driver_sql("BEGIN IMMEDIATE")


# Technical safety bound so numbers always fit in the database (not a business limit).
MAX_PESEWAS = 10**15


class Wallet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str = Field(unique=True, index=True)
    balance: int = 0  # in pesewas
    created_at: str


class Entry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_id: int = Field(foreign_key="wallet.id", index=True)
    kind: str  # deposit, transfer_out, transfer_in
    amount: int  # pesewas
    balance_after: int  # pesewas
    other_wallet_id: Optional[int] = None
    created_at: str


@asynccontextmanager
async def lifespan(_app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Mobile Money Wallets", lifespan=lifespan)


def get_session():
    with Session(engine) as session:
        yield session


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fmt(pesewas: int) -> str:
    return f"{pesewas // 100}.{pesewas % 100:02d}"


def to_pesewas(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise HTTPException(422, "amount must be a number like 10.50")
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation:
        raise HTTPException(422, "amount must be a number like 10.50")
    if not d.is_finite():
        raise HTTPException(422, "amount must be a number like 10.50")
    if d <= 0:
        raise HTTPException(422, "amount must be more than zero")
    if d != d.quantize(Decimal("0.01")):
        raise HTTPException(422, "amount cannot have more than two decimal places")
    p = int(d * 100)
    if p > MAX_PESEWAS:
        raise HTTPException(422, "amount is too large")
    return p


class WalletCreate(BaseModel):
    name: str
    phone: str


class DepositIn(BaseModel):
    amount: Any


class TransferIn(BaseModel):
    to_wallet_id: int
    amount: Any


def wallet_out(w: Wallet) -> dict:
    return {"id": w.id, "name": w.name, "phone": w.phone, "balance": fmt(w.balance),
            "created_at": w.created_at}


def entry_out(e: Entry) -> dict:
    return {"id": e.id, "type": e.kind, "amount": fmt(e.amount),
            "balance_after": fmt(e.balance_after), "other_wallet_id": e.other_wallet_id,
            "created_at": e.created_at}


def load_wallet(session: Session, wallet_id: int) -> Wallet:
    w = session.get(Wallet, wallet_id)
    if not w:
        raise HTTPException(404, "wallet not found")
    return w


@app.post("/wallets", status_code=201)
def create_wallet(data: WalletCreate, session: Session = Depends(get_session)):
    name, phone = data.name.strip(), data.phone.strip()
    if not name:
        raise HTTPException(422, "name is required")
    if not phone:
        raise HTTPException(422, "phone is required")
    if session.exec(select(Wallet).where(Wallet.phone == phone)).first():
        raise HTTPException(409, "this phone number already has a wallet")
    w = Wallet(name=name, phone=phone, balance=0, created_at=now())
    session.add(w)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "this phone number already has a wallet")
    session.refresh(w)
    return wallet_out(w)


@app.get("/wallets/{wallet_id}")
def get_wallet(wallet_id: int, session: Session = Depends(get_session)):
    return wallet_out(load_wallet(session, wallet_id))


@app.post("/wallets/{wallet_id}/deposits", status_code=201)
def deposit(wallet_id: int, data: DepositIn, session: Session = Depends(get_session)):
    amount = to_pesewas(data.amount)
    w = load_wallet(session, wallet_id)
    if w.balance + amount > MAX_PESEWAS * 1000:
        raise HTTPException(422, "amount is too large")
    session.exec(update(Wallet).where(Wallet.id == wallet_id)
                 .values(balance=Wallet.balance + amount))
    session.refresh(w)
    e = Entry(wallet_id=wallet_id, kind="deposit", amount=amount,
              balance_after=w.balance, created_at=now())
    session.add(e)
    session.commit()
    session.refresh(e)
    session.refresh(w)
    return {"wallet": wallet_out(w), "entry": entry_out(e)}


@app.post("/wallets/{wallet_id}/transfers", status_code=201)
def transfer(wallet_id: int, data: TransferIn, session: Session = Depends(get_session)):
    amount = to_pesewas(data.amount)
    if data.to_wallet_id == wallet_id:
        raise HTTPException(400, "you cannot send money to your own wallet")
    sender = load_wallet(session, wallet_id)
    receiver = load_wallet(session, data.to_wallet_id)
    if receiver.balance + amount > MAX_PESEWAS * 1000:
        raise HTTPException(422, "amount is too large")
    res = session.exec(update(Wallet)
                       .where(Wallet.id == wallet_id, Wallet.balance >= amount)
                       .values(balance=Wallet.balance - amount))
    if res.rowcount != 1:
        session.rollback()
        raise HTTPException(400, "not enough money in the wallet")
    session.exec(update(Wallet).where(Wallet.id == receiver.id)
                 .values(balance=Wallet.balance + amount))
    session.refresh(sender)
    session.refresh(receiver)
    ts = now()
    out_e = Entry(wallet_id=sender.id, kind="transfer_out", amount=amount,
                  balance_after=sender.balance, other_wallet_id=receiver.id, created_at=ts)
    in_e = Entry(wallet_id=receiver.id, kind="transfer_in", amount=amount,
                 balance_after=receiver.balance, other_wallet_id=sender.id, created_at=ts)
    session.add(out_e)
    session.add(in_e)
    session.commit()
    session.refresh(out_e)
    session.refresh(sender)
    return {"wallet": wallet_out(sender), "entry": entry_out(out_e)}


@app.get("/wallets/{wallet_id}/history")
def history(wallet_id: int, session: Session = Depends(get_session)):
    load_wallet(session, wallet_id)
    entries = session.exec(select(Entry).where(Entry.wallet_id == wallet_id)
                           .order_by(Entry.id)).all()
    return [entry_out(e) for e in entries]
