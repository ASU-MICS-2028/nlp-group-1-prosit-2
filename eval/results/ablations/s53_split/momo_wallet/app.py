import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./wallets.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
money_lock = threading.Lock()


def now() -> datetime:
    return datetime.now(timezone.utc)


class Wallet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str = Field(unique=True, index=True)
    balance_pesewas: int = 0
    opened_at: datetime = Field(default_factory=now)


class HistoryEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_id: int = Field(foreign_key="wallet.id", index=True)
    type: str  # deposit, sent, received
    amount_pesewas: int
    balance_after_pesewas: int
    other_wallet_id: Optional[int] = None
    created_at: datetime = Field(default_factory=now)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Mobile Money Wallets", lifespan=lifespan)


# ---------- helpers ----------

def to_pesewas(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError("amount must be a number")
    if isinstance(value, float):
        value = repr(value)
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError("amount must be a number")
    if not d.is_finite():
        raise ValueError("amount must be a number")
    if d <= 0:
        raise ValueError("amount must be more than zero")
    if d != d.quantize(Decimal("0.01")):
        raise ValueError("amount must not have more than two decimal places")
    return int(d * 100)


def cedis(pesewas: int) -> str:
    sign = "-" if pesewas < 0 else ""
    p = abs(pesewas)
    return f"{sign}{p // 100}.{p % 100:02d}"


def wallet_out(w: Wallet) -> dict:
    return {
        "wallet_number": w.id,
        "name": w.name,
        "phone": w.phone,
        "balance": cedis(w.balance_pesewas),
        "balance_pesewas": w.balance_pesewas,
        "opened_at": w.opened_at.isoformat(),
    }


def entry_out(e: HistoryEntry) -> dict:
    return {
        "entry_number": e.id,
        "wallet_number": e.wallet_id,
        "type": e.type,
        "amount": cedis(e.amount_pesewas),
        "amount_pesewas": e.amount_pesewas,
        "balance_after": cedis(e.balance_after_pesewas),
        "balance_after_pesewas": e.balance_after_pesewas,
        "other_wallet_number": e.other_wallet_id,
        "created_at": e.created_at.isoformat(),
    }


def get_wallet_or_404(session: Session, number: int) -> Wallet:
    w = session.get(Wallet, number)
    if w is None:
        raise HTTPException(status_code=404, detail=f"Wallet {number} not found")
    return w


# ---------- request bodies ----------

class WalletCreate(BaseModel):
    name: str
    phone: str

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty")
        return v


class DepositIn(BaseModel):
    amount: Any

    @field_validator("amount")
    @classmethod
    def check_amount(cls, v: Any) -> int:
        return to_pesewas(v)


class TransferIn(BaseModel):
    to_wallet_number: int
    amount: Any

    @field_validator("amount")
    @classmethod
    def check_amount(cls, v: Any) -> int:
        return to_pesewas(v)


# ---------- endpoints ----------

@app.post("/wallets", status_code=201)
def open_wallet(body: WalletCreate):
    with Session(engine) as session:
        existing = session.exec(select(Wallet).where(Wallet.phone == body.phone)).first()
        if existing:
            raise HTTPException(status_code=409, detail="This phone number already has a wallet")
        w = Wallet(name=body.name.strip(), phone=body.phone)
        session.add(w)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(status_code=409, detail="This phone number already has a wallet")
        session.refresh(w)
        return wallet_out(w)


@app.get("/wallets/{wallet_number}")
def get_wallet(wallet_number: int):
    with Session(engine) as session:
        return wallet_out(get_wallet_or_404(session, wallet_number))


@app.post("/wallets/{wallet_number}/deposits", status_code=201)
def deposit(wallet_number: int, body: DepositIn):
    amount = body.amount
    with money_lock, Session(engine) as session:
        get_wallet_or_404(session, wallet_number)
        session.exec(
            update(Wallet)
            .where(Wallet.id == wallet_number)
            .values(balance_pesewas=Wallet.balance_pesewas + amount)
        )
        w = session.get(Wallet, wallet_number)
        session.refresh(w)
        e = HistoryEntry(wallet_id=w.id, type="deposit", amount_pesewas=amount,
                         balance_after_pesewas=w.balance_pesewas)
        session.add(e)
        session.commit()
        session.refresh(e)
        session.refresh(w)
        return {"wallet": wallet_out(w), "entry": entry_out(e)}


@app.post("/wallets/{wallet_number}/transfers", status_code=201)
def transfer(wallet_number: int, body: TransferIn):
    amount = body.amount
    if body.to_wallet_number == wallet_number:
        raise HTTPException(status_code=400, detail="You cannot send money to your own wallet")
    with money_lock, Session(engine) as session:
        get_wallet_or_404(session, wallet_number)
        get_wallet_or_404(session, body.to_wallet_number)
        try:
            result = session.exec(
                update(Wallet)
                .where(Wallet.id == wallet_number, Wallet.balance_pesewas >= amount)
                .values(balance_pesewas=Wallet.balance_pesewas - amount)
            )
            if result.rowcount != 1:
                session.rollback()
                raise HTTPException(status_code=400, detail="Not enough money in the wallet")
            session.exec(
                update(Wallet)
                .where(Wallet.id == body.to_wallet_number)
                .values(balance_pesewas=Wallet.balance_pesewas + amount)
            )
            sender = session.get(Wallet, wallet_number)
            receiver = session.get(Wallet, body.to_wallet_number)
            session.refresh(sender)
            session.refresh(receiver)
            sent = HistoryEntry(wallet_id=sender.id, type="sent", amount_pesewas=amount,
                                balance_after_pesewas=sender.balance_pesewas,
                                other_wallet_id=receiver.id)
            received = HistoryEntry(wallet_id=receiver.id, type="received", amount_pesewas=amount,
                                    balance_after_pesewas=receiver.balance_pesewas,
                                    other_wallet_id=sender.id)
            session.add(sent)
            session.add(received)
            session.commit()
        except HTTPException:
            raise
        except Exception:
            session.rollback()
            raise
        session.refresh(sent)
        session.refresh(sender)
        return {"wallet": wallet_out(sender), "entry": entry_out(sent)}


@app.get("/wallets/{wallet_number}/history")
def history(wallet_number: int):
    with Session(engine) as session:
        get_wallet_or_404(session, wallet_number)
        entries = session.exec(
            select(HistoryEntry)
            .where(HistoryEntry.wallet_id == wallet_number)
            .order_by(HistoryEntry.id)
        ).all()
        return [entry_out(e) for e in entries]
