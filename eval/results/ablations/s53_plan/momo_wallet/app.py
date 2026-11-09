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
write_lock = threading.Lock()
MAX_PESEWAS = 2**63 - 1


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Wallet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str = Field(unique=True, index=True)
    balance_pesewas: int = 0
    opened_at: str = Field(default_factory=now)


class HistoryEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_id: int = Field(foreign_key="wallet.id", index=True)
    type: str  # deposit, sent, received
    amount_pesewas: int
    other_wallet_id: Optional[int] = None
    balance_after_pesewas: int
    created_at: str = Field(default_factory=now)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Mobile Money Wallets", lifespan=lifespan)


def cedis(pesewas: int) -> str:
    sign = "-" if pesewas < 0 else ""
    p = abs(pesewas)
    return f"{sign}{p // 100}.{p % 100:02d}"


def parse_amount(v: Any) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise ValueError("amount must be a number like 10 or 10.50")
    try:
        d = Decimal(str(v).strip())
    except (InvalidOperation, ValueError):
        raise ValueError("amount must be a number like 10 or 10.50")
    if not d.is_finite():
        raise ValueError("amount must be a number like 10 or 10.50")
    if d <= 0:
        raise ValueError("amount must be more than zero")
    p = d * 100
    if p != p.to_integral_value():
        raise ValueError("amount cannot have more than two decimal places")
    p = int(p)
    if p > MAX_PESEWAS:
        raise ValueError("amount is too large")
    return p


class WalletCreate(BaseModel):
    name: str
    phone: str

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class DepositIn(BaseModel):
    amount: Any

    @field_validator("amount", mode="before")
    @classmethod
    def check_amount(cls, v):
        return parse_amount(v)


class TransferIn(BaseModel):
    to_phone: str
    amount: Any

    @field_validator("to_phone")
    @classmethod
    def phone_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("amount", mode="before")
    @classmethod
    def check_amount(cls, v):
        return parse_amount(v)


def wallet_out(w: Wallet) -> dict:
    return {
        "wallet_number": w.id,
        "name": w.name,
        "phone": w.phone,
        "balance": cedis(w.balance_pesewas),
        "opened_at": w.opened_at,
    }


def entry_out(e: HistoryEntry) -> dict:
    return {
        "entry_number": e.id,
        "type": e.type,
        "amount": cedis(e.amount_pesewas),
        "other_wallet_number": e.other_wallet_id,
        "balance_after": cedis(e.balance_after_pesewas),
        "date": e.created_at,
    }


def get_wallet_or_404(session: Session, wallet_number: int) -> Wallet:
    w = session.get(Wallet, wallet_number)
    if w is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return w


@app.post("/wallets", status_code=201)
def open_wallet(data: WalletCreate):
    with write_lock, Session(engine) as session:
        if session.exec(select(Wallet).where(Wallet.phone == data.phone)).first():
            raise HTTPException(status_code=409, detail="This phone number already has a wallet")
        w = Wallet(name=data.name, phone=data.phone)
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
def deposit(wallet_number: int, data: DepositIn):
    amount = data.amount
    with write_lock, Session(engine) as session:
        get_wallet_or_404(session, wallet_number)
        result = session.execute(
            update(Wallet)
            .where(Wallet.id == wallet_number)
            .where(Wallet.balance_pesewas <= MAX_PESEWAS - amount)
            .values(balance_pesewas=Wallet.balance_pesewas + amount)
        )
        if result.rowcount != 1:
            session.rollback()
            raise HTTPException(status_code=400, detail="Amount is too large for this wallet")
        w = session.get(Wallet, wallet_number, populate_existing=True)
        entry = HistoryEntry(
            wallet_id=wallet_number,
            type="deposit",
            amount_pesewas=amount,
            balance_after_pesewas=w.balance_pesewas,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        session.refresh(w)
        return {"entry": entry_out(entry), "wallet": wallet_out(w)}


@app.post("/wallets/{wallet_number}/transfers", status_code=201)
def transfer(wallet_number: int, data: TransferIn):
    amount = data.amount
    with write_lock, Session(engine) as session:
        sender = get_wallet_or_404(session, wallet_number)
        receiver = session.exec(select(Wallet).where(Wallet.phone == data.to_phone)).first()
        if receiver is None:
            raise HTTPException(status_code=404, detail="No wallet found for that phone number")
        if receiver.id == sender.id:
            raise HTTPException(status_code=400, detail="You cannot send money to your own wallet")
        sender_id, receiver_id = sender.id, receiver.id
        try:
            r1 = session.execute(
                update(Wallet)
                .where(Wallet.id == sender_id)
                .where(Wallet.balance_pesewas >= amount)
                .values(balance_pesewas=Wallet.balance_pesewas - amount)
            )
            if r1.rowcount != 1:
                session.rollback()
                raise HTTPException(status_code=400, detail="Not enough money in the wallet")
            r2 = session.execute(
                update(Wallet)
                .where(Wallet.id == receiver_id)
                .where(Wallet.balance_pesewas <= MAX_PESEWAS - amount)
                .values(balance_pesewas=Wallet.balance_pesewas + amount)
            )
            if r2.rowcount != 1:
                session.rollback()
                raise HTTPException(status_code=400, detail="Amount is too large for the receiving wallet")
            s = session.get(Wallet, sender_id, populate_existing=True)
            r = session.get(Wallet, receiver_id, populate_existing=True)
            sent = HistoryEntry(
                wallet_id=sender_id, type="sent", amount_pesewas=amount,
                other_wallet_id=receiver_id, balance_after_pesewas=s.balance_pesewas,
            )
            received = HistoryEntry(
                wallet_id=receiver_id, type="received", amount_pesewas=amount,
                other_wallet_id=sender_id, balance_after_pesewas=r.balance_pesewas,
            )
            session.add(sent)
            session.add(received)
            session.commit()
        except HTTPException:
            raise
        except Exception:
            session.rollback()
            raise HTTPException(status_code=500, detail="Transfer failed; no money was moved")
        session.refresh(sent)
        s = session.get(Wallet, sender_id, populate_existing=True)
        return {"entry": entry_out(sent), "wallet": wallet_out(s)}


@app.get("/wallets/{wallet_number}/history")
def history(wallet_number: int):
    with Session(engine) as session:
        get_wallet_or_404(session, wallet_number)
        entries = session.exec(
            select(HistoryEntry).where(HistoryEntry.wallet_id == wallet_number).order_by(HistoryEntry.id)
        ).all()
        return [entry_out(e) for e in entries]
