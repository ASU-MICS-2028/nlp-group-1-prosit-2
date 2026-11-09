import hashlib
import hmac
import re
import secrets
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator

app = FastAPI(title="Accra Shop Mobile Money Wallets")

_lock = threading.Lock()
WALLETS: dict = {}
PHONE_INDEX: dict = {}

MAX_AMOUNT_PESEWAS = 100_000_000_000  # 1 billion cedis per operation
MAX_BALANCE_PESEWAS = 10 ** 15


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fmt(pesewas: int) -> str:
    sign = "-" if pesewas < 0 else ""
    p = abs(pesewas)
    return f"{sign}{p // 100}.{p % 100:02d}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def parse_amount(v: Any) -> int:
    if isinstance(v, bool) or v is None:
        raise ValueError("amount must be a number like 10 or 10.50")
    try:
        if isinstance(v, int):
            d = Decimal(v)
        elif isinstance(v, float):
            d = Decimal(repr(v))
        elif isinstance(v, str):
            s = v.strip()
            if not re.fullmatch(r"\d+(\.\d+)?", s):
                raise ValueError("amount must be a plain positive number like 10 or 10.50")
            d = Decimal(s)
        else:
            raise ValueError("amount must be a number like 10 or 10.50")
    except InvalidOperation:
        raise ValueError("amount is not a valid number")
    if not d.is_finite():
        raise ValueError("amount must be a finite number")
    if d <= 0:
        raise ValueError("amount must be more than zero")
    d = d.normalize()
    if d.as_tuple().exponent < -2:
        raise ValueError("amount cannot have more than two decimal places")
    pesewas = int(d * 100)
    if Decimal(pesewas) != d * 100:
        raise ValueError("amount cannot have more than two decimal places")
    if pesewas <= 0:
        raise ValueError("amount must be more than zero")
    if pesewas > MAX_AMOUNT_PESEWAS:
        raise ValueError("amount is too large")
    return pesewas


def normalize_phone(raw: str) -> str:
    s = re.sub(r"[\s\-()]", "", raw or "")
    if re.fullmatch(r"\+233\d{9}", s):
        return s
    if re.fullmatch(r"233\d{9}", s):
        return "+" + s
    if re.fullmatch(r"00233\d{9}", s):
        return "+" + s[2:]
    if re.fullmatch(r"0\d{9}", s):
        return "+233" + s[1:]
    raise ValueError("phone must be a Ghana number like 0241234567 or +233241234567")


class WalletCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    phone: str

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("name is required")
        if len(v) > 100:
            raise ValueError("name is too long (max 100 characters)")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)


class DepositIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Any

    @field_validator("amount", mode="before")
    @classmethod
    def _amt(cls, v):
        return parse_amount(v)


class TransferIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_wallet_id: str
    to_wallet_id: Optional[str] = None
    to_phone: Optional[str] = None
    amount: Any

    @field_validator("amount", mode="before")
    @classmethod
    def _amt(cls, v):
        return parse_amount(v)

    @field_validator("to_phone")
    @classmethod
    def _phone(cls, v):
        if v is None:
            return v
        return normalize_phone(v)


def public_wallet(w: dict) -> dict:
    return {
        "wallet_id": w["id"],
        "name": w["name"],
        "phone": w["phone"],
        "balance": fmt(w["balance"]),
        "balance_pesewas": w["balance"],
        "currency": "GHS",
        "created_at": w["created_at"],
    }


def get_wallet(wallet_id: str) -> dict:
    w = WALLETS.get(wallet_id)
    if not w:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return w


def authorize(w: dict, token: Optional[str]) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="Missing X-Wallet-Token header for this wallet")
    if not hmac.compare_digest(hash_token(token), w["token_hash"]):
        raise HTTPException(status_code=403, detail="You can only use your own wallet")


def add_entry(w: dict, kind: str, amount: int, **extra) -> dict:
    entry = {
        "entry_id": str(uuid.uuid4()),
        "type": kind,
        "amount": fmt(amount),
        "amount_pesewas": amount,
        "balance_after": fmt(w["balance"]),
        "balance_after_pesewas": w["balance"],
        "timestamp": now_iso(),
    }
    entry.update(extra)
    w["history"].append(entry)
    return entry


@app.get("/")
def root():
    return {"service": "mobile money wallets", "currency": "GHS"}


@app.post("/wallets", status_code=201)
def create_wallet(body: WalletCreate):
    with _lock:
        if body.phone in PHONE_INDEX:
            raise HTTPException(status_code=409, detail="This phone number already has a wallet")
        token = secrets.token_urlsafe(32)
        wid = str(uuid.uuid4())
        w = {
            "id": wid,
            "name": body.name,
            "phone": body.phone,
            "balance": 0,
            "token_hash": hash_token(token),
            "created_at": now_iso(),
            "history": [],
        }
        WALLETS[wid] = w
        PHONE_INDEX[body.phone] = wid
        out = public_wallet(w)
    out["wallet_token"] = token
    out["note"] = "Keep wallet_token secret. Send it in the X-Wallet-Token header to deposit or send money."
    return out


@app.get("/wallets")
def list_wallets():
    with _lock:
        return [public_wallet(w) for w in WALLETS.values()]


@app.get("/wallets/by-phone/{phone}")
def wallet_by_phone(phone: str):
    try:
        p = normalize_phone(phone)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    with _lock:
        wid = PHONE_INDEX.get(p)
        if not wid:
            raise HTTPException(status_code=404, detail="Wallet not found")
        return public_wallet(WALLETS[wid])


@app.get("/wallets/{wallet_id}")
def wallet_info(wallet_id: str):
    with _lock:
        return public_wallet(get_wallet(wallet_id))


@app.get("/wallets/{wallet_id}/balance")
def wallet_balance(wallet_id: str):
    with _lock:
        w = get_wallet(wallet_id)
        return {"wallet_id": w["id"], "balance": fmt(w["balance"]), "balance_pesewas": w["balance"], "currency": "GHS"}


@app.get("/wallets/{wallet_id}/history")
def wallet_history(wallet_id: str):
    with _lock:
        w = get_wallet(wallet_id)
        return {
            "wallet_id": w["id"],
            "balance": fmt(w["balance"]),
            "balance_pesewas": w["balance"],
            "history": [dict(e) for e in w["history"]],
        }


@app.post("/wallets/{wallet_id}/deposit")
def deposit(wallet_id: str, body: DepositIn, x_wallet_token: Optional[str] = Header(default=None)):
    amount: int = body.amount
    with _lock:
        w = get_wallet(wallet_id)
        authorize(w, x_wallet_token)
        if w["balance"] + amount > MAX_BALANCE_PESEWAS:
            raise HTTPException(status_code=400, detail="Deposit would exceed the maximum wallet balance")
        w["balance"] += amount
        entry = add_entry(w, "deposit", amount)
        return {"wallet": public_wallet(w), "entry": entry}


@app.post("/transfers")
def transfer(body: TransferIn, x_wallet_token: Optional[str] = Header(default=None)):
    amount: int = body.amount
    if (body.to_wallet_id is None) == (body.to_phone is None):
        raise HTTPException(status_code=422, detail="Give exactly one of to_wallet_id or to_phone")
    with _lock:
        sender = get_wallet(body.from_wallet_id)
        authorize(sender, x_wallet_token)
        if body.to_wallet_id is not None:
            receiver = WALLETS.get(body.to_wallet_id)
        else:
            rid = PHONE_INDEX.get(body.to_phone)
            receiver = WALLETS.get(rid) if rid else None
        if not receiver:
            raise HTTPException(status_code=404, detail="Receiving wallet not found")
        if receiver["id"] == sender["id"]:
            raise HTTPException(status_code=400, detail="You cannot send money to your own wallet")
        if sender["balance"] < amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        if receiver["balance"] + amount > MAX_BALANCE_PESEWAS:
            raise HTTPException(status_code=400, detail="Transfer would exceed the receiver's maximum balance")
        transfer_id = str(uuid.uuid4())
        sender["balance"] -= amount
        receiver["balance"] += amount
        out_entry = add_entry(sender, "transfer_out", amount, transfer_id=transfer_id,
                              counterparty_wallet_id=receiver["id"], counterparty_name=receiver["name"],
                              counterparty_phone=receiver["phone"])
        add_entry(receiver, "transfer_in", amount, transfer_id=transfer_id,
                  counterparty_wallet_id=sender["id"], counterparty_name=sender["name"],
                  counterparty_phone=sender["phone"])
        return {
            "transfer_id": transfer_id,
            "amount": fmt(amount),
            "amount_pesewas": amount,
            "from_wallet_id": sender["id"],
            "to_wallet_id": receiver["id"],
            "sender_balance_after": fmt(sender["balance"]),
            "entry": out_entry,
        }
