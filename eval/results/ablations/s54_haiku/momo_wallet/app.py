import threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine(
    "sqlite:///./wallet.db", connect_args={"check_same_thread": False}
)
lock = threading.Lock()


class Wallet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str = Field(index=True, unique=True)
    balance_pesewas: int = 0


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    wallet_id: int = Field(index=True)
    kind: str  # "deposit", "transfer_out" or "transfer_in"
    amount_pesewas: int
    balance_after_pesewas: int
    other_wallet_id: Optional[int] = None
    created_at: str


SQLModel.metadata.create_all(engine)

app = FastAPI(title="Mobile Money Wallet")


class WalletIn(BaseModel):
    name: str
    phone: str


class AmountIn(BaseModel):
    amount: Any


class TransferIn(BaseModel):
    from_wallet_id: int
    to_wallet_id: int
    amount: Any


def parse_amount(value: Any) -> int:
    """Convert a cedi amount into whole pesewas, exactly. Refuses bad amounts."""
    if value is None or isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise HTTPException(400, "Amount must be a number of cedis, e.g. 10.50")
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise HTTPException(400, "Amount must be a number of cedis, e.g. 10.50")
    if not d.is_finite():
        raise HTTPException(400, "Amount must be a finite number")
    if d <= 0:
        raise HTTPException(400, "Amount must be more than zero")
    sign, digits, exp = d.normalize().as_tuple()
    if exp < -2:
        raise HTTPException(400, "Amount can have at most two decimal places (pesewas)")
    number = int("".join(str(x) for x in digits)) * (10 ** (exp + 2))
    return number


def fmt(pesewas: int) -> str:
    return f"{pesewas // 100}.{pesewas % 100:02d}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def wallet_out(w: Wallet) -> dict:
    return {
        "id": w.id,
        "name": w.name,
        "phone": w.phone,
        "balance": fmt(w.balance_pesewas),
    }


@app.post("/wallets", status_code=201)
def create_wallet(body: WalletIn):
    name = body.name.strip()
    phone = body.phone.strip()
    if not name:
        raise HTTPException(400, "Name is required")
    if not phone:
        raise HTTPException(400, "Phone number is required")
    with lock, Session(engine, expire_on_commit=False) as s:
        existing = s.exec(select(Wallet).where(Wallet.phone == phone)).first()
        if existing:
            raise HTTPException(409, "A wallet already exists for this phone number")
        w = Wallet(name=name, phone=phone, balance_pesewas=0)
        s.add(w)
        s.commit()
        s.refresh(w)
        return wallet_out(w)


@app.get("/wallets/{wallet_id}")
def get_wallet(wallet_id: int):
    with Session(engine, expire_on_commit=False) as s:
        w = s.get(Wallet, wallet_id)
        if not w:
            raise HTTPException(404, "Wallet not found")
        return wallet_out(w)


@app.post("/wallets/{wallet_id}/deposits", status_code=201)
def deposit(wallet_id: int, body: AmountIn):
    amount = parse_amount(body.amount)
    with lock, Session(engine, expire_on_commit=False) as s:
        w = s.get(Wallet, wallet_id)
        if not w:
            raise HTTPException(404, "Wallet not found")
        w.balance_pesewas += amount
        s.add(w)
        s.add(Transaction(
            wallet_id=w.id,
            kind="deposit",
            amount_pesewas=amount,
            balance_after_pesewas=w.balance_pesewas,
            created_at=now_iso(),
        ))
        s.commit()
        return wallet_out(w)


@app.post("/transfers", status_code=201)
def transfer(body: TransferIn):
    amount = parse_amount(body.amount)
    if body.from_wallet_id == body.to_wallet_id:
        raise HTTPException(400, "You cannot send money to your own wallet")
    with lock, Session(engine, expire_on_commit=False) as s:
        src = s.get(Wallet, body.from_wallet_id)
        dst = s.get(Wallet, body.to_wallet_id)
        if not src or not dst:
            raise HTTPException(404, "Wallet not found")
        if src.balance_pesewas < amount:
            raise HTTPException(400, "Insufficient balance")
        src.balance_pesewas -= amount
        dst.balance_pesewas += amount
        ts = now_iso()
        s.add(src)
        s.add(dst)
        s.add(Transaction(
            wallet_id=src.id, kind="transfer_out", amount_pesewas=amount,
            balance_after_pesewas=src.balance_pesewas,
            other_wallet_id=dst.id, created_at=ts,
        ))
        s.add(Transaction(
            wallet_id=dst.id, kind="transfer_in", amount_pesewas=amount,
            balance_after_pesewas=dst.balance_pesewas,
            other_wallet_id=src.id, created_at=ts,
        ))
        s.commit()
        return {
            "from_wallet": wallet_out(src),
            "to_wallet": wallet_out(dst),
            "amount": fmt(amount),
        }


@app.get("/wallets/{wallet_id}/history")
def history(wallet_id: int):
    with Session(engine, expire_on_commit=False) as s:
        w = s.get(Wallet, wallet_id)
        if not w:
            raise HTTPException(404, "Wallet not found")
        rows = s.exec(
            select(Transaction)
            .where(Transaction.wallet_id == wallet_id)
            .order_by(Transaction.id)
        ).all()
        return {
            "wallet_id": w.id,
            "balance": fmt(w.balance_pesewas),
            "history": [
                {
                    "id": r.id,
                    "type": r.kind,
                    "amount": fmt(r.amount_pesewas),
                    "balance_after": fmt(r.balance_after_pesewas),
                    "other_wallet_id": r.other_wallet_id,
                    "created_at": r.created_at,
                }
                for r in rows
            ],
        }
