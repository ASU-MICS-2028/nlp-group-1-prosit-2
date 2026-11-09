import threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///wallet.db", connect_args={"check_same_thread": False})
lock = threading.Lock()
MAX_PESEWAS = 10**15


class Wallet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str = Field(unique=True, index=True)
    balance: int = 0  # pesewas


class Entry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_id: int = Field(index=True)
    type: str  # deposit, transfer_out, transfer_in
    amount: int  # pesewas
    balance_after: int  # pesewas
    counterparty_phone: Optional[str] = None
    created_at: str


SQLModel.metadata.create_all(engine)
app = FastAPI()


def to_pesewas(v) -> int:
    if isinstance(v, bool) or v is None:
        raise ValueError("amount must be a number")
    try:
        d = Decimal(str(v)) if not isinstance(v, Decimal) else v
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


def cedis(p: int) -> float:
    return p / 100


class AmountIn(BaseModel):
    amount: Decimal

    @field_validator("amount", mode="before")
    @classmethod
    def check(cls, v):
        to_pesewas(v)
        return v


class TransferIn(AmountIn):
    to_phone: str


class WalletIn(BaseModel):
    name: str
    phone: str

    @field_validator("name", "phone")
    @classmethod
    def nonblank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


def wallet_json(w):
    return {"name": w.name, "phone": w.phone, "balance": cedis(w.balance)}


def get_wallet(s, phone):
    w = s.exec(select(Wallet).where(Wallet.phone == phone.strip())).first()
    if not w:
        raise HTTPException(404, f"No wallet for phone number {phone}")
    return w


def now():
    return datetime.now(timezone.utc).isoformat()


def entry_json(e):
    return {
        "id": e.id,
        "type": e.type,
        "amount": cedis(e.amount),
        "balance_after": cedis(e.balance_after),
        "counterparty_phone": e.counterparty_phone,
        "created_at": e.created_at,
    }


@app.post("/wallets", status_code=201)
def open_wallet(body: WalletIn):
    with lock, Session(engine) as s:
        if s.exec(select(Wallet).where(Wallet.phone == body.phone)).first():
            raise HTTPException(409, "A wallet already exists for this phone number")
        w = Wallet(name=body.name, phone=body.phone)
        s.add(w)
        s.commit()
        s.refresh(w)
        return wallet_json(w)


@app.get("/wallets/{phone}")
def balance(phone: str):
    with Session(engine) as s:
        return wallet_json(get_wallet(s, phone))


@app.post("/wallets/{phone}/deposits", status_code=201)
def deposit(phone: str, body: AmountIn):
    p = to_pesewas(body.amount)
    with lock, Session(engine) as s:
        w = get_wallet(s, phone)
        w.balance += p
        e = Entry(wallet_id=w.id, type="deposit", amount=p,
                  balance_after=w.balance, created_at=now())
        s.add(w)
        s.add(e)
        s.commit()
        s.refresh(e)
        return entry_json(e)


@app.post("/wallets/{phone}/transfers", status_code=201)
def transfer(phone: str, body: TransferIn):
    p = to_pesewas(body.amount)
    to_phone = body.to_phone.strip()
    with lock, Session(engine) as s:
        src = get_wallet(s, phone)
        if src.phone == to_phone:
            raise HTTPException(400, "You cannot send money to your own wallet")
        dst = get_wallet(s, to_phone)
        if src.balance < p:
            raise HTTPException(400, "Insufficient balance")
        src.balance -= p
        dst.balance += p
        out = Entry(wallet_id=src.id, type="transfer_out", amount=p,
                    balance_after=src.balance, counterparty_phone=dst.phone,
                    created_at=now())
        inn = Entry(wallet_id=dst.id, type="transfer_in", amount=p,
                    balance_after=dst.balance, counterparty_phone=src.phone,
                    created_at=now())
        s.add(src)
        s.add(dst)
        s.add(out)
        s.add(inn)
        s.commit()
        s.refresh(out)
        return entry_json(out)


@app.get("/wallets/{phone}/transactions")
def history(phone: str):
    with Session(engine) as s:
        w = get_wallet(s, phone)
        es = s.exec(select(Entry).where(Entry.wallet_id == w.id).order_by(Entry.id)).all()
        return [entry_json(e) for e in es]
