import hashlib
import hmac
import re
import secrets
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

app = FastAPI(title="Accra Shop Mobile Money Wallet")

# ---------------------------------------------------------------------------
# Storage (in memory). All money is stored as whole integers of pesewas,
# so there can never be rounding errors.
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_wallets: Dict[str, Dict[str, Any]] = {}
_phone_index: Dict[str, str] = {}
_history: Dict[str, List[Dict[str, Any]]] = {}

MAX_AMOUNT_PESEWAS = 100_000_000_00  # 100 million cedis per single operation
MAX_BALANCE_PESEWAS = 10_000_000_000_00


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt(pesewas: int) -> str:
    sign = "-" if pesewas < 0 else ""
    p = abs(pesewas)
    return f"{sign}{p // 100}.{p % 100:02d}"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


_AMOUNT_RE = re.compile(r"^\d+(\.\d+)?$")


def parse_amount(v: Any) -> int:
    """Convert an incoming amount to whole pesewas, refusing anything invalid."""
    if isinstance(v, bool) or v is None:
        raise ValueError("amount must be a number of cedis, e.g. \"12.50\"")
    try:
        if isinstance(v, int):
            d = Decimal(v)
        elif isinstance(v, float):
            if v != v or v in (float("inf"), float("-inf")):
                raise ValueError("amount must be a finite number")
            d = Decimal(repr(v))
        elif isinstance(v, str):
            s = v.strip()
            if not _AMOUNT_RE.match(s):
                raise ValueError("amount must be a positive number like \"12.50\"")
            d = Decimal(s)
        else:
            raise ValueError("amount must be a number of cedis, e.g. \"12.50\"")
    except InvalidOperation:
        raise ValueError("amount is not a valid number")
    if not d.is_finite():
        raise ValueError("amount must be a finite number")
    if d <= 0:
        raise ValueError("amount must be more than zero")
    if d != d.quantize(Decimal("0.01")):
        raise ValueError("amount cannot have more than two decimal places (pesewas)")
    pesewas = int(d * 100)
    if pesewas <= 0:
        raise ValueError("amount must be more than zero")
    if pesewas > MAX_AMOUNT_PESEWAS:
        raise ValueError("amount is too large")
    return pesewas


def normalize_phone(raw: Any) -> str:
    if not isinstance(raw, str):
        raise ValueError("phone must be text")
    s = re.sub(r"[\s\-().]", "", raw)
    if s.startswith("+233"):
        rest = s[4:]
    elif s.startswith("00233"):
        rest = s[5:]
    elif s.startswith("233") and len(s) == 12:
        rest = s[3:]
    elif s.startswith("0") and len(s) == 10:
        rest = s[1:]
    else:
        raise ValueError("phone must be a Ghana number like 0241234567 or +233241234567")
    if not re.fullmatch(r"[1-9]\d{8}", rest):
        raise ValueError("phone must be a Ghana number like 0241234567 or +233241234567")
    return "+233" + rest


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class WalletCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    phone: str

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name is required")
        if len(v) > 100:
            raise ValueError("name is too long (max 100 characters)")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)


class DepositRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Any

    @field_validator("amount", mode="before")
    @classmethod
    def _amount(cls, v: Any) -> int:
        return parse_amount(v)


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Any
    to_phone: Optional[str] = None
    to_wallet_id: Optional[str] = None
    note: Optional[str] = None

    @field_validator("amount", mode="before")
    @classmethod
    def _amount(cls, v: Any) -> int:
        return parse_amount(v)

    @field_validator("to_phone")
    @classmethod
    def _phone(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else normalize_phone(v)

    @field_validator("note")
    @classmethod
    def _note(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if len(v) > 200:
            raise ValueError("note is too long (max 200 characters)")
        return v or None

    @model_validator(mode="after")
    def _one_target(self):
        if (self.to_phone is None) == (self.to_wallet_id is None):
            raise ValueError("give exactly one of to_phone or to_wallet_id")
        return self


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _public(w: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": w["id"],
        "name": w["name"],
        "phone": w["phone"],
        "balance": _fmt(w["balance"]),
        "balance_pesewas": w["balance"],
        "currency": "GHS",
        "created_at": w["created_at"],
    }


def _get_wallet(wallet_id: str) -> Dict[str, Any]:
    w = _wallets.get(wallet_id)
    if w is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return w


def _check_owner(w: Dict[str, Any], token: Optional[str]) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="Missing X-Wallet-Token header (the wallet owner's secret token)")
    if not hmac.compare_digest(_hash_token(token), w["token_hash"]):
        raise HTTPException(status_code=403, detail="This token does not belong to this wallet")


def _entry(wallet_id: str, kind: str, amount: int, balance_after: int, **extra) -> Dict[str, Any]:
    e = {
        "id": str(uuid.uuid4()),
        "type": kind,
        "amount": _fmt(amount),
        "amount_pesewas": amount,
        "balance_after": _fmt(balance_after),
        "balance_after_pesewas": balance_after,
        "currency": "GHS",
        "timestamp": _now(),
    }
    e.update(extra)
    _history[wallet_id].append(e)
    return e


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/wallets", status_code=201)
def create_wallet(body: WalletCreate):
    with _lock:
        if body.phone in _phone_index:
            raise HTTPException(status_code=409, detail="A wallet already exists for this phone number")
        wid = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        w = {
            "id": wid,
            "name": body.name,
            "phone": body.phone,
            "balance": 0,
            "created_at": _now(),
            "token_hash": _hash_token(token),
        }
        _wallets[wid] = w
        _phone_index[body.phone] = wid
        _history[wid] = []
        result = _public(w)
        result["token"] = token
        result["token_note"] = "Keep this secret. Send it in the X-Wallet-Token header to deposit or send money from this wallet."
        return result


@app.get("/wallets")
def list_wallets():
    with _lock:
        return [_public(w) for w in _wallets.values()]


@app.get("/wallets/by-phone/{phone}")
def wallet_by_phone(phone: str):
    try:
        p = normalize_phone(phone)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    with _lock:
        wid = _phone_index.get(p)
        if wid is None:
            raise HTTPException(status_code=404, detail="Wallet not found")
        return _public(_wallets[wid])


@app.get("/wallets/{wallet_id}")
def get_wallet(wallet_id: str):
    with _lock:
        return _public(_get_wallet(wallet_id))


@app.get("/wallets/{wallet_id}/balance")
def get_balance(wallet_id: str):
    with _lock:
        w = _get_wallet(wallet_id)
        return {"wallet_id": w["id"], "balance": _fmt(w["balance"]), "balance_pesewas": w["balance"], "currency": "GHS"}


@app.get("/wallets/{wallet_id}/history")
def get_history(wallet_id: str):
    with _lock:
        w = _get_wallet(wallet_id)
        return {
            "wallet_id": w["id"],
            "balance": _fmt(w["balance"]),
            "balance_pesewas": w["balance"],
            "currency": "GHS",
            "history": [dict(e) for e in _history[wallet_id]],
        }


@app.post("/wallets/{wallet_id}/deposit")
def deposit(wallet_id: str, body: DepositRequest, x_wallet_token: Optional[str] = Header(None, alias="X-Wallet-Token")):
    with _lock:
        w = _get_wallet(wallet_id)
        _check_owner(w, x_wallet_token)
        amount: int = body.amount
        new_balance = w["balance"] + amount
        if new_balance > MAX_BALANCE_PESEWAS:
            raise HTTPException(status_code=400, detail="Deposit would exceed the maximum wallet balance")
        w["balance"] = new_balance
        e = _entry(wallet_id, "deposit", amount, new_balance)
        return {"transaction": e, "wallet": _public(w)}


@app.post("/wallets/{wallet_id}/transfer")
def transfer(wallet_id: str, body: TransferRequest, x_wallet_token: Optional[str] = Header(None, alias="X-Wallet-Token")):
    with _lock:
        sender = _get_wallet(wallet_id)
        _check_owner(sender, x_wallet_token)
        if body.to_wallet_id is not None:
            rid = body.to_wallet_id
            if rid not in _wallets:
                raise HTTPException(status_code=404, detail="Recipient wallet not found")
        else:
            rid = _phone_index.get(body.to_phone)
            if rid is None:
                raise HTTPException(status_code=404, detail="No wallet found for the recipient phone number")
        if rid == sender["id"]:
            raise HTTPException(status_code=400, detail="You cannot send money to your own wallet")
        recipient = _wallets[rid]
        amount: int = body.amount
        if amount > sender["balance"]:
            raise HTTPException(status_code=400, detail=f"Insufficient funds: balance is {_fmt(sender['balance'])} GHS")
        if recipient["balance"] + amount > MAX_BALANCE_PESEWAS:
            raise HTTPException(status_code=400, detail="Transfer would exceed the recipient's maximum wallet balance")
        transfer_id = str(uuid.uuid4())
        sender["balance"] -= amount
        recipient["balance"] += amount
        out_e = _entry(sender["id"], "transfer_out", amount, sender["balance"], transfer_id=transfer_id,
                       counterparty_wallet_id=recipient["id"], counterparty_name=recipient["name"],
                       counterparty_phone=recipient["phone"], note=body.note)
        _entry(recipient["id"], "transfer_in", amount, recipient["balance"], transfer_id=transfer_id,
               counterparty_wallet_id=sender["id"], counterparty_name=sender["name"],
               counterparty_phone=sender["phone"], note=body.note)
        return {"transfer_id": transfer_id, "transaction": out_e, "wallet": _public(sender)}
