import re
import threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

MAX_PESEWAS = 2**62


class Wallet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str = Field(unique=True, index=True)
    balance: int = 0  # pesewas


class Entry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_id: int = Field(index=True)
    kind: str  # deposit, transfer_out, transfer_in
    amount: int  # pesewas
    balance_after: int  # pesewas
    counterparty_wallet_id: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


engine = create_engine("sqlite:///wallet.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)
lock = threading.Lock()

app = FastAPI(title="Shop Wallet")


def money(p: int) -> str:
    return f"{p // 100}.{p % 100:02d}"


def normalize_phone(raw: str) -> str:
    s = re.sub(r"[\s\-()]", "", raw)
    if s.startswith("+233"):
        rest = s[4:]
    elif s.startswith("233"):
        rest = s[3:]
    elif s.startswith("0"):
        rest = s[1:]
    else:
        raise ValueError("phone must be a Ghana number like 024 123 4567 or +233 24 123 4567")
    if not re.fullmatch(r"[1-9]\d{8}", rest):
        raise ValueError("phone must be a Ghana number like 024 123 4567 or +233 24 123 4567")
    return "+233" + rest


def parse_amount(v) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, float, str, Decimal)):
        raise ValueError("amount must be a number")
    try:
        d = Decimal(str(v).strip())
    except InvalidOperation:
        raise ValueError("amount must be a number")
    if not d.is_finite():
        raise ValueError("amount must be a number")
    if d <= 0:
        raise ValueError("amount must be more than zero")
    if d != d.quantize(Decimal("0.01")):
        raise ValueError("amount can have at most two decimal places")
    p = int(d * 100)
    if p > MAX_PESEWAS:
        raise ValueError("amount is too large")
    return p


class WalletIn(BaseModel):
    name: str
    phone: str

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name is required")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        return normalize_phone(v)


class DepositIn(BaseModel):
    amount: int | float | str

    @field_validator("amount", mode="before")
    @classmethod
    def _amount(cls, v):
        return parse_amount(v)


class TransferIn(DepositIn):
    to_wallet_id: int


def wallet_out(w: Wallet) -> dict:
    return {"id": w.id, "name": w.name, "phone": w.phone, "balance": money(w.balance)}


def entry_out(e: Entry) -> dict:
    return {
        "id": e.id,
        "type": e.kind,
        "amount": money(e.amount),
        "balance_after": money(e.balance_after),
        "counterparty_wallet_id": e.counterparty_wallet_id,
        "created_at": e.created_at.isoformat(),
    }


def get_wallet(s: Session, wid: int) -> Wallet:
    w = s.get(Wallet, wid)
    if not w:
        raise HTTPException(404, "Wallet not found")
    return w


@app.post("/wallets", status_code=201)
def create_wallet(body: WalletIn):
    with lock, Session(engine) as s:
        if s.exec(select(Wallet).where(Wallet.phone == body.phone)).first():
            raise HTTPException(409, "This phone number already has a wallet")
        w = Wallet(name=body.name, phone=body.phone)
        s.add(w)
        s.commit()
        s.refresh(w)
        return wallet_out(w)


@app.get("/wallets/{wallet_id}")
def read_wallet(wallet_id: int):
    with Session(engine) as s:
        return wallet_out(get_wallet(s, wallet_id))


@app.post("/wallets/{wallet_id}/deposits", status_code=201)
def deposit(wallet_id: int, body: DepositIn):
    with lock, Session(engine) as s:
        w = get_wallet(s, wallet_id)
        if w.balance + body.amount > MAX_PESEWAS:
            raise HTTPException(400, "Balance too large")
        w.balance += body.amount
        e = Entry(wallet_id=w.id, kind="deposit", amount=body.amount, balance_after=w.balance)
        s.add(w)
        s.add(e)
        s.commit()
        s.refresh(e)
        return entry_out(e)


@app.post("/wallets/{wallet_id}/transfers", status_code=201)
def transfer(wallet_id: int, body: TransferIn):
    with lock, Session(engine) as s:
        src = get_wallet(s, wallet_id)
        if body.to_wallet_id == wallet_id:
            raise HTTPException(400, "Cannot send money to your own wallet")
        dst = get_wallet(s, body.to_wallet_id)
        if src.balance < body.amount:
            raise HTTPException(400, "Insufficient balance")
        if dst.balance + body.amount > MAX_PESEWAS:
            raise HTTPException(400, "Recipient balance too large")
        src.balance -= body.amount
        dst.balance += body.amount
        out = Entry(wallet_id=src.id, kind="transfer_out", amount=body.amount,
                    balance_after=src.balance, counterparty_wallet_id=dst.id)
        inn = Entry(wallet_id=dst.id, kind="transfer_in", amount=body.amount,
                    balance_after=dst.balance, counterparty_wallet_id=src.id)
        s.add(src)
        s.add(dst)
        s.add(out)
        s.add(inn)
        s.commit()
        s.refresh(out)
        return entry_out(out)


@app.get("/wallets/{wallet_id}/transactions")
def history(wallet_id: int):
    with Session(engine) as s:
        get_wallet(s, wallet_id)
        rows = s.exec(select(Entry).where(Entry.wallet_id == wallet_id).order_by(Entry.id)).all()
        return [entry_out(e) for e in rows]
