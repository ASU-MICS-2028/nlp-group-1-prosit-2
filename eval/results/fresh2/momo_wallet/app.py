import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./wallets.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Technical limit only, so numbers always fit in the database (far beyond any real amount).
MAX_PESEWAS = 2**62


class Wallet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str = Field(unique=True, index=True)
    balance_pesewas: int = 0
    created_at: str


class Entry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_id: int = Field(index=True, foreign_key="wallet.id")
    type: str  # deposit, transfer_out, transfer_in
    amount_pesewas: int
    balance_after_pesewas: int
    counterparty_wallet_id: Optional[int] = None
    created_at: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Mobile Money Wallets", lifespan=lifespan)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def cedis(pesewas: int) -> float:
    return pesewas / 100


def normalize_phone(raw: str) -> str:
    p = re.sub(r"[\s\-()]", "", raw)
    if p.startswith("+233"):
        p = "0" + p[4:]
    elif p.startswith("233") and len(p) == 12:
        p = "0" + p[3:]
    if not re.fullmatch(r"0\d{9}", p):
        raise ValueError(
            "phone must be a Ghana number like 0241234567 or +233241234567"
        )
    return p


def parse_amount(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("amount must be a number")
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation:
        raise ValueError("amount must be a number")
    if not d.is_finite():
        raise ValueError("amount must be a number")
    if d != d.quantize(Decimal("0.01"), rounding="ROUND_DOWN"):
        raise ValueError("amount can have at most two decimal places")
    if d <= 0:
        raise ValueError("amount must be more than zero")
    pesewas = int(d * 100)
    if pesewas > MAX_PESEWAS:
        raise ValueError("amount is too large")
    return pesewas


class WalletCreate(BaseModel):
    name: str
    phone: str

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name is required")
        return v

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str) -> str:
        return normalize_phone(v)


class DepositIn(BaseModel):
    amount: Any

    @field_validator("amount")
    @classmethod
    def check_amount(cls, v: Any) -> int:
        return parse_amount(v)


class TransferIn(BaseModel):
    to_wallet_id: int
    amount: Any

    @field_validator("amount")
    @classmethod
    def check_amount(cls, v: Any) -> int:
        return parse_amount(v)


def wallet_out(w: Wallet) -> dict:
    return {
        "id": w.id,
        "name": w.name,
        "phone": w.phone,
        "balance": cedis(w.balance_pesewas),
        "created_at": w.created_at,
    }


def entry_out(e: Entry) -> dict:
    return {
        "id": e.id,
        "type": e.type,
        "amount": cedis(e.amount_pesewas),
        "balance_after": cedis(e.balance_after_pesewas),
        "counterparty_wallet_id": e.counterparty_wallet_id,
        "created_at": e.created_at,
    }


def get_wallet_or_404(session: Session, wallet_id: int) -> Wallet:
    w = session.get(Wallet, wallet_id)
    if not w:
        raise HTTPException(404, "wallet not found")
    return w


def current_balance(session: Session, wallet_id: int) -> int:
    return session.execute(
        text("SELECT balance_pesewas FROM wallet WHERE id = :id"), {"id": wallet_id}
    ).scalar_one()


@app.post("/wallets", status_code=201)
def create_wallet(data: WalletCreate):
    with Session(engine) as session:
        if session.exec(select(Wallet).where(Wallet.phone == data.phone)).first():
            raise HTTPException(409, "this phone number already has a wallet")
        w = Wallet(name=data.name, phone=data.phone, balance_pesewas=0, created_at=now())
        session.add(w)
        try:
            session.commit()
        except IntegrityError:
            raise HTTPException(409, "this phone number already has a wallet")
        session.refresh(w)
        return wallet_out(w)


@app.get("/wallets/{wallet_id}")
def get_wallet(wallet_id: int):
    with Session(engine) as session:
        return wallet_out(get_wallet_or_404(session, wallet_id))


@app.get("/wallets/{wallet_id}/transactions")
def get_history(wallet_id: int):
    with Session(engine) as session:
        get_wallet_or_404(session, wallet_id)
        entries = session.exec(
            select(Entry).where(Entry.wallet_id == wallet_id).order_by(Entry.id)
        ).all()
        return [entry_out(e) for e in entries]


@app.post("/wallets/{wallet_id}/deposits", status_code=201)
def deposit(wallet_id: int, data: DepositIn):
    amount = data.amount
    with Session(engine) as session:
        get_wallet_or_404(session, wallet_id)
        res = session.execute(
            text(
                "UPDATE wallet SET balance_pesewas = balance_pesewas + :a "
                "WHERE id = :id AND balance_pesewas + :a <= :max"
            ),
            {"a": amount, "id": wallet_id, "max": MAX_PESEWAS},
        )
        if res.rowcount != 1:
            session.rollback()
            raise HTTPException(400, "amount is too large")
        bal = current_balance(session, wallet_id)
        e = Entry(
            wallet_id=wallet_id, type="deposit", amount_pesewas=amount,
            balance_after_pesewas=bal, created_at=now(),
        )
        session.add(e)
        session.commit()
        session.refresh(e)
        return entry_out(e)


@app.post("/wallets/{wallet_id}/transfers", status_code=201)
def transfer(wallet_id: int, data: TransferIn):
    amount = data.amount
    to_id = data.to_wallet_id
    with Session(engine) as session:
        get_wallet_or_404(session, wallet_id)
        if to_id == wallet_id:
            raise HTTPException(400, "you cannot send money to your own wallet")
        if not session.get(Wallet, to_id):
            raise HTTPException(404, "receiving wallet not found")
        res = session.execute(
            text(
                "UPDATE wallet SET balance_pesewas = balance_pesewas - :a "
                "WHERE id = :id AND balance_pesewas >= :a"
            ),
            {"a": amount, "id": wallet_id},
        )
        if res.rowcount != 1:
            session.rollback()
            raise HTTPException(400, "insufficient balance")
        res = session.execute(
            text(
                "UPDATE wallet SET balance_pesewas = balance_pesewas + :a "
                "WHERE id = :id AND balance_pesewas + :a <= :max"
            ),
            {"a": amount, "id": to_id, "max": MAX_PESEWAS},
        )
        if res.rowcount != 1:
            session.rollback()
            raise HTTPException(400, "amount is too large")
        ts = now()
        out = Entry(
            wallet_id=wallet_id, type="transfer_out", amount_pesewas=amount,
            balance_after_pesewas=current_balance(session, wallet_id),
            counterparty_wallet_id=to_id, created_at=ts,
        )
        inc = Entry(
            wallet_id=to_id, type="transfer_in", amount_pesewas=amount,
            balance_after_pesewas=current_balance(session, to_id),
            counterparty_wallet_id=wallet_id, created_at=ts,
        )
        session.add(out)
        session.add(inc)
        session.commit()
        session.refresh(out)
        return entry_out(out)
