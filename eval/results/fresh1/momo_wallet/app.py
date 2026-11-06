import threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./wallets.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
money_lock = threading.Lock()
MAX_PESEWAS = 2**63 - 1  # largest value SQLite can store


class Wallet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str = Field(index=True, unique=True)
    balance_pesewas: int = 0
    created_at: str


class Entry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_id: int = Field(index=True, foreign_key="wallet.id")
    kind: str  # deposit, transfer_out, transfer_in
    amount_pesewas: int
    balance_after_pesewas: int
    counterparty_phone: Optional[str] = None
    created_at: str


app = FastAPI(title="Mobile Money Wallet")


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


SQLModel.metadata.create_all(engine)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_cedis(pesewas: int) -> str:
    sign = "-" if pesewas < 0 else ""
    p = abs(pesewas)
    return f"{sign}{p // 100}.{p % 100:02d}"


def parse_amount(value) -> int:
    if isinstance(value, bool):
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
    if d > Decimal(MAX_PESEWAS) / 100:
        raise ValueError("amount is too large")
    pesewas = d * 100
    if pesewas != pesewas.to_integral_value():
        raise ValueError("amount can have at most two decimal places")
    pesewas = int(pesewas)
    if pesewas > MAX_PESEWAS:
        raise ValueError("amount is too large")
    return pesewas


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
    amount: object

    @field_validator("amount")
    @classmethod
    def check_amount(cls, v):
        return parse_amount(v)


class TransferIn(BaseModel):
    to_phone: str
    amount: object

    @field_validator("to_phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("amount")
    @classmethod
    def check_amount(cls, v):
        return parse_amount(v)


def wallet_out(w: Wallet) -> dict:
    return {"name": w.name, "phone": w.phone, "balance": to_cedis(w.balance_pesewas),
            "created_at": w.created_at}


def entry_out(e: Entry) -> dict:
    return {"id": e.id, "type": e.kind, "amount": to_cedis(e.amount_pesewas),
            "balance_after": to_cedis(e.balance_after_pesewas),
            "counterparty_phone": e.counterparty_phone, "created_at": e.created_at}


def get_wallet(session: Session, phone: str) -> Wallet:
    w = session.exec(select(Wallet).where(Wallet.phone == phone.strip())).first()
    if not w:
        raise HTTPException(404, "Wallet not found")
    return w


@app.post("/wallets", status_code=201)
def create_wallet(data: WalletCreate):
    with money_lock, Session(engine) as s:
        if s.exec(select(Wallet).where(Wallet.phone == data.phone)).first():
            raise HTTPException(409, "A wallet with this phone number already exists")
        w = Wallet(name=data.name, phone=data.phone, created_at=now())
        s.add(w)
        s.commit()
        s.refresh(w)
        return wallet_out(w)


@app.get("/wallets/{phone}")
def read_wallet(phone: str):
    with Session(engine) as s:
        return wallet_out(get_wallet(s, phone))


@app.post("/wallets/{phone}/deposits", status_code=201)
def deposit(phone: str, data: DepositIn):
    with money_lock, Session(engine) as s:
        w = get_wallet(s, phone)
        new_balance = w.balance_pesewas + data.amount
        if new_balance > MAX_PESEWAS:
            raise HTTPException(422, "Balance would be too large")
        w.balance_pesewas = new_balance
        e = Entry(wallet_id=w.id, kind="deposit", amount_pesewas=data.amount,
                  balance_after_pesewas=new_balance, created_at=now())
        s.add(w)
        s.add(e)
        s.commit()
        s.refresh(w)
        s.refresh(e)
        return {"wallet": wallet_out(w), "entry": entry_out(e)}


@app.post("/wallets/{phone}/transfers", status_code=201)
def transfer(phone: str, data: TransferIn):
    with money_lock, Session(engine) as s:
        sender = get_wallet(s, phone)
        if data.to_phone == sender.phone:
            raise HTTPException(400, "You cannot send money to your own wallet")
        receiver = s.exec(select(Wallet).where(Wallet.phone == data.to_phone)).first()
        if not receiver:
            raise HTTPException(404, "Receiving wallet not found")
        if data.amount > sender.balance_pesewas:
            raise HTTPException(400, "Not enough money in wallet")
        if receiver.balance_pesewas + data.amount > MAX_PESEWAS:
            raise HTTPException(422, "Receiver balance would be too large")
        sender.balance_pesewas -= data.amount
        receiver.balance_pesewas += data.amount
        ts = now()
        out_e = Entry(wallet_id=sender.id, kind="transfer_out", amount_pesewas=data.amount,
                      balance_after_pesewas=sender.balance_pesewas,
                      counterparty_phone=receiver.phone, created_at=ts)
        in_e = Entry(wallet_id=receiver.id, kind="transfer_in", amount_pesewas=data.amount,
                     balance_after_pesewas=receiver.balance_pesewas,
                     counterparty_phone=sender.phone, created_at=ts)
        s.add_all([sender, receiver, out_e, in_e])
        s.commit()
        s.refresh(sender)
        s.refresh(out_e)
        return {"wallet": wallet_out(sender), "entry": entry_out(out_e)}


@app.get("/wallets/{phone}/history")
def history(phone: str):
    with Session(engine) as s:
        w = get_wallet(s, phone)
        entries = s.exec(select(Entry).where(Entry.wallet_id == w.id).order_by(Entry.id)).all()
        return {"phone": w.phone, "balance": to_cedis(w.balance_pesewas),
                "history": [entry_out(e) for e in entries]}
