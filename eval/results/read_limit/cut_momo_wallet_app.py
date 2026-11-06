import re
import secrets
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Accra Shop Mobile Money Wallet")

_lock = threading.RLock()
_wallets: Dict[str, dict] = {}
_phone_index: Dict[str, str] = {}

MAX_PESEWAS = 100_000_000_000_00  # 100 billion cedis safety cap


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt(pesewas: int) -> str:
    sign = "-" if pesewas < 0 else ""
    p = abs(pesewas)
    return f"{sign}{p // 100}.{p % 100:02d}"


def _parse_amount(value: Any) -> int:
    if value is None or isinstance(value, bool):
        raise HTTPException(status_code=422, detail="Amount is required and must be a number like 12.50")
    if isinstance(value, (int, float, str)):
        text = str(value).strip()
    elif isinstance(value, Decimal):
        text = str(value)
    else:
        raise HTTPException(status_code=422, detail="Amount must be a number like 12.50")
    if not re.fullmatch(r"\+?\d+(\.\d+)?|\+?\.\d+", text):
        raise HTTPException(status_code=422, detail="Amount must be a plain positive number like 12.50")
    try:
        d = Decimal(text)
    except InvalidOperation:
        raise HTTPException(status_code=422, detail="Amount is not a valid number")
    if not d.is_finite():
        raise HTTPException(status_code=422, detail="Amount is not a valid number")
    if d.as_tuple().exponent < -2 and d != d.quantize(Decimal("0.01")):
        raise HTTPException(status_code=422, detail="Amount cannot have more than two decimal places")
    pesewas_d = d * 100
    if pesewas_d != pesewas_d.to_integral_value():
        raise HTTPException(status_code=422, detail="Amount cannot have more than two decimal places")
    pesewas = int(pesewas_d)
    if pesewas <= 0:
        raise HTTPException(status_code=422, detail="Amount must be more than zero")
    if pesewas > MAX_PESEWAS:
        raise HTTPException(status_code=422, detail="Amount is too large")
    return pesewas


MAX_NOTE_LENGTH = 100


def _parse_note(note: Any) -> Optional[str]:
    if note is None:
        return None
    if not isinstance(note, str):
        raise HTTPException(status_code=422, detail="Note must be text")
    note = note.strip()
    if not note:
        return None
    if len(note) > MAX_NOTE_LENGTH:
        raise HTTPException(status_code=422, detail=f"Note cannot be longer than {MAX_NOTE_LENGTH} characters")
    return note


def _normalize_phone(phone: Any) -> str:
    if not isinstance(phone, str):
        raise HTTPException(status_code=422, detail="Phone number must be text")
    p = re.sub(r"[\s\-()]", "", phone)
    if p.startswith("+233"):
        p = "0" + p[4:]
    elif p.startswith("00233"):
        p = "0" + p[5:]
    elif p.startswith("233") and len(p) == 12:
        p = "0" + p[3:]
    elif len(p) == 9 and p.isdigit():
        p = "0" + p
    if not re.fullmatch(r"0\d{9}", p):
        raise HTTPException(status_code=422, detail="Phone number must be a valid Ghana number, e.g. 0241234567 or +233241234567")
    return p


def _get_wallet(wallet_id: str) -> dict:
    w = _wallets.get(wallet_id)
    if w is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return w


def _check_owner(w: dict, token: Optional[str]) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="Missing X-Wallet-Token header")
    if not secrets.compare_digest(str(token), w["token"]):
        raise HTTPException(status_code=403, detail="This token does not belong to this wallet")


def _public(w: dict) -> dict:
    return {
        "wallet_id": w["id"],
        "name": w["name"],
        "phone": w["phone"],
        "balance": _fmt(w["balance"]),
        "balance_pesewas": w["balance"],
        "currency": "GHS",
        "created_at": w["created_at"],
    }


def _entry_out(e: dict) -> dict:
    return {
        "entry_id": e["entry_id"],
        "transaction_id": e["transaction_id"],
        "type": e["type"],
        "amount": _fmt(e["amount"]),
        "amount_pesewas": e["amount"],
        "balance_after": _fmt(e["balance_after"]),
        "balance_after_pesewas": e["balance_after"],
        "counterparty_wallet_id": e.get("counterparty_wallet_id"),
        "counterparty_name": e.get("counterparty_name"),
        "counterparty_phone": e.get("counterparty_phone"),
        "note": e.get("note"),
        "currency": "GHS",
        "timestamp": e["timestamp"],
    }


class WalletCreate(BaseModel):
    name: Any = None
    phone: Any = None


class DepositIn(BaseModel):
    amount: Any = None
    note: Any = None


class TransferIn(BaseModel):
    amount: Any = None
    note: Any = None
    to_wallet_id: Optional[str] = None
    to_phone: Optional[str] = None


@app.post("/wallets", status_code=201)
def create_wallet(body: WalletCreate):
    if not isinstance(body.name, str) or not body.name.strip():
        raise HTTPException(status_code=422, detail="Name is required")
    name = body.name.strip()
    if len(name) > 100:
        raise HTTPException(status_code=422, detail="Name is too long")
    phone = _normalize_phone(body.phone)
    with _lock:
        if phone in _phone_index:
            raise HTTPException(status_code=409, detail="A wallet already exists for this phone number")
        wid = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        w = {"id": wid, "name": name, "phone": phone, "balance": 0, "token": token,
             "created_at": _now(), "history": []}
        _wallets[wid] = w
        _phone_index[phone] = wid
        out = _public(w)
        out["token"] = token
        out["note"] = "Keep this token secret. Send it in the X-Wallet-Token header to deposit or send money."
        return out


@app.get("/wallets/by-phone/{phone}")
def wallet_by_phone(phone: str):
    p = _normalize_phone(phone)
    with _lock:
        wid = _phone_index.get(p)
        if not wid:
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
        return {"wallet_id": w["id"], "balance": _fmt(w["balance"]), "balance_pesewas": w["balance"],
                "currency": "GHS", "history": [_entry_out(e) for e in w["history"]]}


@app.post("/wallets/{wallet_id}/deposit")
def deposit(wallet_id: str, body: DepositIn, x_wallet_token: Optional[str] = Header(default=None)):
    amount = _parse_amount(body.amount)
    note = _parse_note(body.note)
    with _lock:
        w = _get_wallet(wallet_id)
        _check_owner(w, x_wallet_token)
        if w["balance"] + amount > MAX_PESEWAS:
            raise HTTPException(status_code=422, detail="Balance would exceed the maximum allowed")
        w["balance"] += amount
        txid = str(uuid.uuid4())
        e = {"entry_id": str(uuid.uuid4()), "transaction_id": txid, "type": "deposit", "amount": amount,
             "balance_after": w["balance"], "note": note, "timestamp": _now()}
        w["history"].append(e)
        return {"transaction_id": txid, "wallet": _public(w), "entry": _entry_out(e)}


@app.post("/wallets/{wallet_id}/transfer")
def transfer(wallet_id: str, body: TransferIn, x_wallet_token: Optional[str] = Header(default=None)):
    amount = _parse_amount(body.amount)
    note = _parse_note(body.note)
    if not body.to_wallet_id and not body.to_phone:
        raise HTTPException(status_code=422, detail="Give to_wallet_id or to_phone for the receiver")
    with _lock:
        sender = _get_wallet(wallet_id)
        _check_owner(sender, x_wallet_token)
        receiver = None
        if body.to_wallet_id:
            receiver = _wallets.get(body.to_wallet_id)
            if receiver is None:
                raise HTTPException(status_code=404, detail="Receiving wallet not found")
        if body.to_phone:
            p = _normalize_phone(body.to_phone)
            rid = _phone_index.get(p)
            if rid is None:
                raise HTTPException(status_code=404, detail="No wallet for that phone number")
            if receiver is not None and receiver["id"] != rid:
                raise HTTPException(status_code=422, detail="to_wallet_id and to_phone point to different wallets")
            receiver = _wallets[rid]
        if receiver["id"] == sender["id"]:
            raise HTTPException(status_code=400, detail="You cannot send money to your own wallet")
        if amount > sender["balance"]:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        if receiver["balance"] + amount > MAX_PESEWAS:
            raise HTTPException(status_code=422, detail="Receiver balance would exceed the maximum allowed")
        sender["balance"] -= amount
        receiver["balance"] += amount
        txid = str(uuid.uuid4())
        ts = _now()
        se = {"entry_id": str(uuid.uuid4()), "transaction_id": txid, "type": "transfer_out", "amount": amount,
              "balance_after": sender["balance"], "counterparty_wallet_id": receiver["id"],
              "counterparty_name": receiver["name"], "counterparty_phone": receiver["phone"], "note": note,
              "timestamp": ts}
        re_ = {"entry_id": str(uuid.uuid4()), "transaction_id": txid, "type": "transfer_in", "amount": amount,
               "balance_after": receiver["balance"], "counterparty_wallet_id": sender["id"],
               "counterparty_name": sender["name"], "counterparty_phone": sender["phone"], "note": note,
               "timestamp": ts}
        sender["history"].append(se)
        receiver["history"].append(re_)
        return {"transaction_id": txid, "amount": _fmt(amount), "amount_pesewas": amount,
                "from_wallet_id": sender["id"], "to_wallet_id": receiver["id"],
                "sender_balance": _fmt(sender["balance"]), "sender_balance_pesewas": sender["balance"],
                "entry": _entry_out(se)}
