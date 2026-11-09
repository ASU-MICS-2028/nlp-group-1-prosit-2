import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, update

DB_URL = "sqlite:///./wallets.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False, "timeout": 30})

MAX_PESEWAS = 2**63 - 1  # largest value SQLite can store


# ---------- database tables ----------
class Wallet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str = Field(unique=True, index=True)
    balance: int = 0  # in pesewas
    created_at: str


class Entry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_id: int = Field(index=True, foreign_key="wallet.id")
    kind: str  # deposit | transfer_in | transfer_out
    amount: int  # pesewas
    balance_after: int  # pesewas
    counterparty_wallet_id: Optional[int] = None
    created_at: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Mobile Money Wallets", lifespan=lifespan)


# ---------- helpers ----------
def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def cedis(p: int) -> str:
    return f"{p // 100}.{p % 100:02d}"


def normalize_phone(raw: str) -> str:
    """Accept Ghana numbers as 0XXXXXXXXX, 233XXXXXXXXX or +233XXXXXXXXX
    (spaces, dashes and brackets ignored). Stored as +233XXXXXXXXX so the
    same number written differently counts as the same wallet."""
    s = re.sub(r"[\s\-()]", "", raw or "")
    m = re.fullmatch(r"(?:\+233|233|0)([1-9]\d{8})", s)
    if not m:
        raise ValueError(
            "phone must be a Ghana number like 0244123456 or +233244123456"
        )
    return "+233" + m.group(1)


def to_pesewas(amount: Decimal) -> int:
    if not amount.is_finite():
        raise ValueError("amount must be a number")
    if amount <= 0:
        raise ValueError("amount must be more than zero")
    if amount.as_tuple().exponent < -2 and amount != amount.quantize(Decimal("0.01")):
        raise ValueError("amount can have at most two decimal places")
    p = int(amount * 100)
    if p > MAX_PESEWAS:
        raise ValueError("amount is too large")
    return p


def wallet_out(w: Wallet) -> dict:
    return {
        "id": w.id,
        "name": w.name,
        "phone": w.phone,
        "balance": cedis(w.balance),
        "created_at": w.created_at,
    }


def entry_out(e: Entry) -> dict:
    return {
        "id": e.id,
        "type": e.kind,
        "amount": cedis(e.amount),
        "balance_after": cedis(e.balance_after),
        "counterparty_wallet_id": e.counterparty_wallet_id,
        "created_at": e.created_at,
    }


def get_balance(session: Session, wallet_id: int) -> int:
    return session.exec(select(Wallet.balance).where(Wallet.id == wallet_id)).one()


# ---------- request bodies ----------
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


class AmountIn(BaseModel):
    amount: Decimal = PField(description="Cedis, e.g. 12.50")

    @field_validator("amount")
    @classmethod
    def check_amount(cls, v: Decimal) -> Decimal:
        to_pesewas(v)
        return v


class TransferIn(AmountIn):
    from_wallet_id: int
    to_wallet_id: int


# ---------- endpoints ----------
@app.post("/wallets", status_code=201)
def open_wallet(body: WalletCreate):
    with Session(engine) as session:
        if session.exec(select(Wallet).where(Wallet.phone == body.phone)).first():
            raise HTTPException(409, "A wallet with this phone number already exists")
        w = Wallet(name=body.name, phone=body.phone, balance=0, created_at=now())
        session.add(w)
        try:
            session.commit()
        except Exception:
            session.rollback()
            raise HTTPException(409, "A wallet with this phone number already exists")
        session.refresh(w)
        return wallet_out(w)


@app.get("/wallets/{wallet_id}")
def get_wallet(wallet_id: int):
    with Session(engine) as session:
        w = session.get(Wallet, wallet_id)
        if not w:
            raise HTTPException(404, "Wallet not found")
        return wallet_out(w)


@app.get("/wallets/{wallet_id}/history")
def wallet_history(wallet_id: int):
    with Session(engine) as session:
        w = session.get(Wallet, wallet_id)
        if not w:
            raise HTTPException(404, "Wallet not found")
        entries = session.exec(
            select(Entry).where(Entry.wallet_id == wallet_id).order_by(Entry.id)
        ).all()
        return {
            "wallet_id": w.id,
            "balance": cedis(w.balance),
            "history": [entry_out(e) for e in entries],
        }


@app.post("/wallets/{wallet_id}/deposits", status_code=201)
def deposit(wallet_id: int, body: AmountIn):
    amount = to_pesewas(body.amount)
    with Session(engine) as session:
        if not session.get(Wallet, wallet_id):
            raise HTTPException(404, "Wallet not found")
        res = session.exec(
            update(Wallet)
            .where(Wallet.id == wallet_id, Wallet.balance <= MAX_PESEWAS - amount)
            .values(balance=Wallet.balance + amount)
        )
        if res.rowcount != 1:
            session.rollback()
            raise HTTPException(400, "Deposit would make the balance too large to store")
        e = Entry(
            wallet_id=wallet_id,
            kind="deposit",
            amount=amount,
            balance_after=get_balance(session, wallet_id),
            created_at=now(),
        )
        session.add(e)
        session.commit()
        session.refresh(e)
        return entry_out(e)


@app.post("/transfers", status_code=201)
def transfer(body: TransferIn):
    amount = to_pesewas(body.amount)
    if body.from_wallet_id == body.to_wallet_id:
        raise HTTPException(400, "You cannot send money to your own wallet")
    with Session(engine) as session:
        if not session.get(Wallet, body.from_wallet_id):
            raise HTTPException(404, "Sending wallet not found")
        if not session.get(Wallet, body.to_wallet_id):
            raise HTTPException(404, "Receiving wallet not found")

        debit = session.exec(
            update(Wallet)
            .where(Wallet.id == body.from_wallet_id, Wallet.balance >= amount)
            .values(balance=Wallet.balance - amount)
        )
        if debit.rowcount != 1:
            session.rollback()
            raise HTTPException(400, "Insufficient balance")
        credit = session.exec(
            update(Wallet)
            .where(Wallet.id == body.to_wallet_id, Wallet.balance <= MAX_PESEWAS - amount)
            .values(balance=Wallet.balance + amount)
        )
        if credit.rowcount != 1:
            session.rollback()
            raise HTTPException(400, "Transfer would make the receiver's balance too large to store")

        ts = now()
        out_e = Entry(
            wallet_id=body.from_wallet_id,
            kind="transfer_out",
            amount=amount,
            balance_after=get_balance(session, body.from_wallet_id),
            counterparty_wallet_id=body.to_wallet_id,
            created_at=ts,
        )
        in_e = Entry(
            wallet_id=body.to_wallet_id,
            kind="transfer_in",
            amount=amount,
            balance_after=get_balance(session, body.to_wallet_id),
            counterparty_wallet_id=body.from_wallet_id,
            created_at=ts,
        )
        session.add(out_e)
        session.add(in_e)
        session.commit()
        session.refresh(out_e)
        session.refresh(in_e)
        return {
            "from_wallet_id": body.from_wallet_id,
            "to_wallet_id": body.to_wallet_id,
            "amount": cedis(amount),
            "sender_balance_after": cedis(out_e.balance_after),
            "receiver_balance_after": cedis(in_e.balance_after),
            "created_at": ts,
        }
