"""Mobile money wallet service (Ghana cedis).

All money is stored as whole pesewas (integers) so totals are always exact.
Amounts are shown in responses as strings with two decimals, e.g. "12.50".
"""
import os
import re
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Session, SQLModel, create_engine, select

DB_FILE = os.environ.get("WALLET_DB", "wallet.db")
engine = create_engine(f"sqlite:///{DB_FILE}", connect_args={"check_same_thread": False})
money_lock = threading.Lock()  # one money movement at a time

MAX_AMOUNT_PESEWAS = 10**14  # technical ceiling so numbers always fit in the database


# ---------- database tables ----------
class Wallet(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("phone"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str = Field(index=True)
    balance_pesewas: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Entry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_id: int = Field(index=True, foreign_key="wallet.id")
    kind: str  # deposit | transfer_in | transfer_out
    amount_pesewas: int
    balance_after_pesewas: int
    other_wallet_id: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------- helpers ----------
def to_pesewas(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError("amount must be a number")
    if isinstance(value, float):
        value = repr(value)
    if isinstance(value, (int, str)):
        try:
            d = Decimal(str(value).strip())
        except InvalidOperation:
            raise ValueError("amount must be a number")
    elif isinstance(value, Decimal):
        d = value
    else:
        raise ValueError("amount must be a number")
    if not d.is_finite():
        raise ValueError("amount must be a number")
    if d <= 0:
        raise ValueError("amount must be more than zero")
    if d != d.quantize(Decimal("0.01")):
        raise ValueError("amount can have at most two decimal places")
    pesewas = int(d * 100)
    if pesewas > MAX_AMOUNT_PESEWAS:
        raise ValueError("amount is too large")
    return pesewas


def cedis(pesewas: int) -> str:
    sign = "-" if pesewas < 0 else ""
    p = abs(pesewas)
    return f"{sign}{p // 100}.{p % 100:02d}"


def normalize_phone(raw: str) -> str:
    p = re.sub(r"[\s\-()]", "", raw or "")
    if not re.fullmatch(r"\+?\d{9,15}", p):
        raise ValueError("phone must be a valid phone number")
    if p.startswith("+"):
        return p
    if p.startswith("233"):
        return "+" + p
    if p.startswith("0") and len(p) == 10:
        return "+233" + p[1:]
    if len(p) == 9:
        return "+233" + p
    return "+" + p


def wallet_out(w: Wallet) -> dict:
    return {"id": w.id, "name": w.name, "phone": w.phone, "balance": cedis(w.balance_pesewas)}


def entry_out(e: Entry) -> dict:
    return {
        "id": e.id,
        "type": e.kind,
        "amount": cedis(e.amount_pesewas),
        "balance_after": cedis(e.balance_after_pesewas),
        "other_wallet_id": e.other_wallet_id,
        "created_at": e.created_at.isoformat(),
    }


def get_wallet_or_404(session: Session, wallet_id: int) -> Wallet:
    w = session.get(Wallet, wallet_id)
    if not w:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return w


# ---------- request bodies ----------
class WalletIn(BaseModel):
    name: str
    phone: str

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name is required")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)


class DepositIn(BaseModel):
    amount: Any

    @field_validator("amount", mode="before")
    @classmethod
    def _amount(cls, v):
        return to_pesewas(v)


class TransferIn(BaseModel):
    to_wallet_id: int
    amount: Any

    @field_validator("amount", mode="before")
    @classmethod
    def _amount(cls, v):
        return to_pesewas(v)


# ---------- app ----------
@asynccontextmanager
async def lifespan(_: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Mobile Money Wallets", lifespan=lifespan)


@app.post("/wallets", status_code=201)
def open_wallet(body: WalletIn):
    with money_lock, Session(engine) as s:
        if s.exec(select(Wallet).where(Wallet.phone == body.phone)).first():
            raise HTTPException(status_code=409, detail="This phone number already has a wallet")
        w = Wallet(name=body.name, phone=body.phone)
        s.add(w)
        s.commit()
        s.refresh(w)
        return wallet_out(w)


@app.get("/wallets/{wallet_id}")
def get_wallet(wallet_id: int):
    with Session(engine) as s:
        return wallet_out(get_wallet_or_404(s, wallet_id))


@app.post("/wallets/{wallet_id}/deposits", status_code=201)
def deposit(wallet_id: int, body: DepositIn):
    amount = body.amount
    with money_lock, Session(engine) as s:
        w = get_wallet_or_404(s, wallet_id)
        w.balance_pesewas += amount
        e = Entry(wallet_id=w.id, kind="deposit", amount_pesewas=amount,
                  balance_after_pesewas=w.balance_pesewas)
        s.add(w)
        s.add(e)
        s.commit()
        s.refresh(w)
        s.refresh(e)
        return {"wallet": wallet_out(w), "entry": entry_out(e)}


@app.post("/wallets/{wallet_id}/transfers", status_code=201)
def transfer(wallet_id: int, body: TransferIn):
    amount = body.amount
    with money_lock, Session(engine) as s:
        sender = get_wallet_or_404(s, wallet_id)
        if body.to_wallet_id == sender.id:
            raise HTTPException(status_code=400, detail="You cannot send money to your own wallet")
        receiver = s.get(Wallet, body.to_wallet_id)
        if not receiver:
            raise HTTPException(status_code=404, detail="Receiving wallet not found")
        if sender.balance_pesewas < amount:
            raise HTTPException(status_code=400, detail="Not enough money in the wallet")
        sender.balance_pesewas -= amount
        receiver.balance_pesewas += amount
        out_e = Entry(wallet_id=sender.id, kind="transfer_out", amount_pesewas=amount,
                      balance_after_pesewas=sender.balance_pesewas, other_wallet_id=receiver.id)
        in_e = Entry(wallet_id=receiver.id, kind="transfer_in", amount_pesewas=amount,
                     balance_after_pesewas=receiver.balance_pesewas, other_wallet_id=sender.id)
        s.add_all([sender, receiver, out_e, in_e])
        s.commit()
        s.refresh(sender)
        s.refresh(out_e)
        return {"wallet": wallet_out(sender), "entry": entry_out(out_e)}


@app.get("/wallets/{wallet_id}/history")
def history(wallet_id: int):
    with Session(engine) as s:
        w = get_wallet_or_404(s, wallet_id)
        entries = s.exec(select(Entry).where(Entry.wallet_id == w.id).order_by(Entry.id)).all()
        return {"wallet": wallet_out(w), "history": [entry_out(e) for e in entries]}
