import hmac
import hashlib
import re
import secrets
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Accra Shop Mobile Money Wallets")

_lock = threading.Lock()
_wallets: Dict[str, dict] = {}
_phone_index: Dict[str, str] = {}

MAX_PESEWAS_PER_OPERATION = 100_000_000_000  # 1,000,000,000.00 GHS


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt(pesewas: int) -> str:
    sign = "-" if pesewas < 0 else ""
    p = abs(pesewas)
    return f"{sign}{p // 100}.{p % 100:02d}"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_phone(raw: Any) -> str:
    if not isinstance(raw, str):
        raise HTTPException(status_code=422, detail="Phone number must be text, e.g. '0241234567'.")
    s = re.sub(r"[\s\-()]", "", raw.strip())
    if s.startswith("+233"):
        s = "0" + s[4:]
    elif s.startswith("00233"):
        s = "0" + s[5:]
    elif s.startswith("233") and len(s) == 12:
        s = "0" + s[3:]
    if not re.fullmatch(r"0\d{9}", s):
        raise HTTPException(status_code=422, detail="Invalid Ghana phone number. Use e.g. 0241234567 or +233241234567.")
    return s


def _parse_amount(raw: Any) -> int:
    """Convert an amount in cedis to an exact integer number of pesewas."""
    if isinstance(raw, bool) or raw is None:
        raise HTTPException(status_code=422, detail="Amount must be a number of cedis, e.g. 12.50.")
    try:
        if isinstance(raw, int):
            d = Decimal(raw)
        elif isinstance(raw, float):
            d = Decimal(repr(raw))
        elif isinstance(raw, str):
            s = raw.strip()
            if not s or len(s) > 30:
                raise HTTPException(status_code=422, detail="Amount must be a number of cedis, e.g. 12.50.")
            d = Decimal(s)
        else:
            raise HTTPException(status_code=422, detail="Amount must be a number of cedis, e.g. 12.50.")
    except InvalidOperation:
        raise HTTPException(status_code=422, detail="Amount must be a number of cedis, e.g. 12.50.")
    if not d.is_finite():
        raise HTTPException(status_code=422, detail="Amount must be a finite number.")
    if d <= 0:
        raise HTTPException(status_code=422, detail="Amount must be more than zero.")
    if d != d.quantize(Decimal("0.01")):
        raise HTTPException(status_code=422, detail="Amount cannot have more than two decimal places (pesewas).")
    pesewas = int(d * 100)
    if pesewas <= 0:
        raise HTTPException(status_code=422, detail="Amount must be more than zero.")
    if pesewas > MAX_PESEWAS_PER_OPERATION:
        raise HTTPException(status_code=422, detail="Amount is too large.")
    return pesewas


class WalletCreate(BaseModel):
    name: Any = None
    phone: Any = None


class DepositIn(BaseModel):
    amount: Any = None


class TransferIn(BaseModel):
    amount: Any = None
    to_phone: Optional[Any] = None
    to_wallet_id: Optional[Any] = None


def _public(w: dict) -> dict:
    return {
        "id": w["id"],
        "name": w["name"],
        "phone": w["phone"],
        "balance": _fmt(w["balance"]),
        "currency": "GHS",
        "created_at": w["created_at"],
    }


def _get_wallet(wallet_id: str) -> dict:
    w = _wallets.get(wallet_id)
    if w is None:
        raise HTTPException(status_code=404, detail="Wallet not found.")
    return w


def _authorize(w: dict, token: Optional[str]) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="Missing X-Wallet-Token header. Only the wallet owner can do this.")
    if not hmac.compare_digest(_hash_token(token), w["token_hash"]):
        raise HTTPException(status_code=403, detail="This token does not belong to this wallet.")


@app.post("/wallets", status_code=201)
def open_wallet(body: WalletCreate):
    if not isinstance(body.name, str) or not body.name.strip():
        raise HTTPException(status_code=422, detail="Name is required.")
    name = " ".join(body.name.split())
    if len(name) > 100:
        raise HTTPException(status_code=422, detail="Name is too long (max 100 characters).")
    phone = _normalize_phone(body.phone)
    token = secrets.token_urlsafe(32)
    with _lock:
        if phone in _phone_index:
            raise HTTPException(status_code=409, detail="A wallet already exists for this phone number.")
        wid = str(uuid.uuid4())
        w = {
            "id": wid,
            "name": name,
            "phone": phone,
            "balance": 0,
            "history": [],
            "token_hash": _hash_token(token),
            "created_at": _now(),
        }
        _wallets[wid] = w
        _phone_index[phone] = wid
        result = _public(w)
    result["token"] = token
    result["note"] = "Keep this token secret. Send it in the X-Wallet-Token header to deposit or send money."
    return result


@app.get("/wallets")
def list_wallets():
    with _lock:
        return [_public(w) for w in _wallets.values()]


@app.get("/wallets/by-phone/{phone}")
def wallet_by_phone(phone: str):
    p = _normalize_phone(phone)
    with _lock:
        wid = _phone_index.get(p)
        if wid is None:
            raise HTTPException(status_code=404, detail="No wallet for this phone number.")
        return _public(_wallets[wid])


@app.get("/wallets/{wallet_id}")
def get_wallet(wallet_id: str):
    with _lock:
        return _public(_get_wallet(wallet_id))


@app.get("/wallets/{wallet_id}/balance")
def get_balance(wallet_id: str):
    with _lock:
        w = _get_wallet(wallet_id)
        return {"id": w["id"], "phone": w["phone"], "balance": _fmt(w["balance"]), "currency": "GHS"}


@app.get("/wallets/{wallet_id}/history")
def get_history(wallet_id: str):
    with _lock:
        w = _get_wallet(wallet_id)
        return {
            "id": w["id"],
            "phone": w["phone"],
            "balance": _fmt(w["balance"]),
            "currency": "GHS",
            "history": [
                {**{k: v for k, v in e.items() if k not in ("amount", "balance_after")},
                 "amount": _fmt(e["amount"]),
                 "balance_after": _fmt(e["balance_after"])}
                for e in w["history"]
            ],
        }


@app.post("/wallets/{wallet_id}/deposits", status_code=201)
def deposit(wallet_id: str, body: DepositIn, x_wallet_token: Optional[str] = Header(default=None)):
    amount = _parse_amount(body.amount)
    with _lock:
        w = _get_wallet(wallet_id)
        _authorize(w, x_wallet_token)
        w["balance"] += amount
        entry = {
            "id": str(uuid.uuid4()),
            "type": "deposit",
            "amount": amount,
            "balance_after": w["balance"],
            "timestamp": _now(),
        }
        w["history"].append(entry)
        return {
            "transaction_id": entry["id"],
            "type": "deposit",
            "amount": _fmt(amount),
            "balance_after": _fmt(w["balance"]),
            "currency": "GHS",
        }


@app.post("/wallets/{wallet_id}/transfers", status_code=201)
def transfer(wallet_id: str, body: TransferIn, x_wallet_token: Optional[str] = Header(default=None)):
    amount = _parse_amount(body.amount)
    if body.to_phone is None and body.to_wallet_id is None:
        raise HTTPException(status_code=422, detail="Give the receiver's to_phone or to_wallet_id.")
    to_phone = _normalize_phone(body.to_phone) if body.to_phone is not None else None
    if body.to_wallet_id is not None and not isinstance(body.to_wallet_id, str):
        raise HTTPException(status_code=422, detail="to_wallet_id must be text.")
    with _lock:
        sender = _get_wallet(wallet_id)
        _authorize(sender, x_wallet_token)
        receiver_id = None
        if to_phone is not None:
            receiver_id = _phone_index.get(to_phone)
            if receiver_id is None:
                raise HTTPException(status_code=404, detail="No wallet for the receiver's phone number.")
        if body.to_wallet_id is not None:
            if body.to_wallet_id not in _wallets:
                raise HTTPException(status_code=404, detail="Receiver wallet not found.")
            if receiver_id is not None and receiver_id != body.to_wallet_id:
                raise HTTPException(status_code=422, detail="to_phone and to_wallet_id point to different wallets.")
            receiver_id = body.to_wallet_id
        receiver = _wallets[receiver_id]
        if receiver["id"] == sender["id"]:
            raise HTTPException(status_code=400, detail="You cannot send money to your own wallet.")
        if sender["balance"] < amount:
            raise HTTPException(status_code=400, detail=f"Insufficient funds. Balance is {_fmt(sender['balance'])} GHS.")
        transfer_id = str(uuid.uuid4())
        ts = _now()
        sender["balance"] -= amount
        receiver["balance"] += amount
        sender["history"].append({
            "id": transfer_id,
            "type": "transfer_out",
            "amount": amount,
            "balance_after": sender["balance"],
            "counterparty_wallet_id": receiver["id"],
            "counterparty_phone": receiver["phone"],
            "counterparty_name": receiver["name"],
            "timestamp": ts,
        })
        receiver["history"].append({
            "id": transfer_id,
            "type": "transfer_in",
            "amount": amount,
            "balance_after": receiver["balance"],
            "counterparty_wallet_id": sender["id"],
            "counterparty_phone": sender["phone"],
            "counterparty_name": sender["name"],
            "timestamp": ts,
        })
        return {
            "transaction_id": transfer_id,
            "type": "transfer",
            "amount": _fmt(amount),
            "from_wallet_id": sender["id"],
            "to_wallet_id": receiver["id"],
            "to_phone": receiver["phone"],
            "balance_after": _fmt(sender["balance"]),
            "currency": "GHS",
        }
