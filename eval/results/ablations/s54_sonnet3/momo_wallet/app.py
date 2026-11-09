import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator, condecimal
from sqlalchemy import update
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///wallet.db", connect_args={"check_same_thread": False})


class Wallet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str = Field(unique=True, index=True)
    balance: int = 0  # pesewas


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_id: int = Field(index=True)
    type: str  # deposit, transfer_out, transfer_in
    amount: int  # pesewas
    balance_after: int  # pesewas
    counterparty_wallet_id: Optional[int] = None
    created_at: str


SQLModel.metadata.create_all(engine)

app = FastAPI()

Money = condecimal(gt=Decimal(0), decimal_places=2, max_digits=12, allow_inf_nan=False)


class WalletIn(BaseModel):
    name: str
    phone: str

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name required")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        s = re.sub(r"[ \-()]", "", v)
        m = re.fullmatch(r"(?:\+233|233|0)(\d{9})", s)
        if not m:
            raise ValueError("invalid Ghana phone number")
        return "+233" + m.group(1)


class DepositIn(BaseModel):
    amount: Money


class TransferIn(BaseModel):
    to_wallet_id: int
    amount: Money


def fmt(p: int) -> str:
    return f"{p // 100}.{p % 100:02d}"


def pesewas(d: Decimal) -> int:
    return int(d * 100)


def wallet_out(w: Wallet):
    return {"id": w.id, "name": w.name, "phone": w.phone, "balance": fmt(w.balance)}


def tx_out(t: Transaction):
    return {
        "id": t.id,
        "type": t.type,
        "amount": fmt(t.amount),
        "balance_after": fmt(t.balance_after),
        "counterparty_wallet_id": t.counterparty_wallet_id,
        "created_at": t.created_at,
    }


def now():
    return datetime.now(timezone.utc).isoformat()


def get_wallet(s: Session, wid: int) -> Wallet:
    w = s.get(Wallet, wid)
    if not w:
        raise HTTPException(404, "Wallet not found")
    return w


@app.post("/wallets", status_code=201)
def create_wallet(body: WalletIn):
    with Session(engine) as s:
        if s.exec(select(Wallet).where(Wallet.phone == body.phone)).first():
            raise HTTPException(409, "Phone number already has a wallet")
        w = Wallet(name=body.name, phone=body.phone)
        s.add(w)
        s.commit()
        s.refresh(w)
        return wallet_out(w)


@app.get("/wallets/{wallet_id}")
def read_wallet(wallet_id: int):
    with Session(engine) as s:
        return wallet_out(get_wallet(s, wallet_id))


@app.get("/wallets/{wallet_id}/transactions")
def history(wallet_id: int):
    with Session(engine) as s:
        get_wallet(s, wallet_id)
        rows = s.exec(
            select(Transaction).where(Transaction.wallet_id == wallet_id).order_by(Transaction.id)
        ).all()
        return [tx_out(t) for t in rows]


@app.post("/wallets/{wallet_id}/deposits", status_code=201)
def deposit(wallet_id: int, body: DepositIn):
    a = pesewas(body.amount)
    with Session(engine) as s:
        get_wallet(s, wallet_id)
        s.exec(update(Wallet).where(Wallet.id == wallet_id).values(balance=Wallet.balance + a))
        bal = s.get(Wallet, wallet_id)
        s.refresh(bal)
        t = Transaction(wallet_id=wallet_id, type="deposit", amount=a,
                        balance_after=bal.balance, created_at=now())
        s.add(t)
        s.commit()
        s.refresh(t)
        return tx_out(t)


@app.post("/wallets/{wallet_id}/transfers", status_code=201)
def transfer(wallet_id: int, body: TransferIn):
    a = pesewas(body.amount)
    if body.to_wallet_id == wallet_id:
        raise HTTPException(400, "Cannot send money to your own wallet")
    with Session(engine) as s:
        get_wallet(s, wallet_id)
        get_wallet(s, body.to_wallet_id)
        res = s.exec(
            update(Wallet)
            .where(Wallet.id == wallet_id, Wallet.balance >= a)
            .values(balance=Wallet.balance - a)
        )
        if res.rowcount != 1:
            s.rollback()
            raise HTTPException(400, "Insufficient balance")
        s.exec(update(Wallet).where(Wallet.id == body.to_wallet_id).values(balance=Wallet.balance + a))
        src = s.get(Wallet, wallet_id)
        dst = s.get(Wallet, body.to_wallet_id)
        s.refresh(src)
        s.refresh(dst)
        ts = now()
        out = Transaction(wallet_id=wallet_id, type="transfer_out", amount=a,
                          balance_after=src.balance,
                          counterparty_wallet_id=body.to_wallet_id, created_at=ts)
        inn = Transaction(wallet_id=body.to_wallet_id, type="transfer_in", amount=a,
                          balance_after=dst.balance,
                          counterparty_wallet_id=wallet_id, created_at=ts)
        s.add(out)
        s.add(inn)
        s.commit()
        s.refresh(out)
        return tx_out(out)
