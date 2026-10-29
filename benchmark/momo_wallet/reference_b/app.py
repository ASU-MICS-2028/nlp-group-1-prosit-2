# Second correct backend for momo_wallet, making other valid choices than reference/:
# text ids (uuid4 hex), 200 for creation, 422 for refusals, money returned as text like "10.50", other paths and names.
import uuid
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()
wallets, entries = {}, []


class WalletIn(BaseModel):
    owner_name: str
    phone_number: str


class MoneyIn(BaseModel):
    amount_ghs: Decimal = Field(gt=0, decimal_places=2)


class SendIn(MoneyIn):
    sender_id: str
    receiver_id: str


def text(d):
    return f"{d:.2f}"


def find(wid):
    if wid not in wallets:
        raise HTTPException(404, "Wallet not found")
    return wallets[wid]


def show(w):
    return {**w, "balance_ghs": text(w["balance_ghs"])}


def record(w, kind, amount):
    entries.append({"wallet_id": w["id"], "kind": kind, "amount_ghs": text(amount), "balance_ghs_after": text(w["balance_ghs"])})


@app.post("/wallets")
def open_wallet(w: WalletIn):
    if any(x["phone_number"] == w.phone_number for x in wallets.values()):
        raise HTTPException(422, "Phone number already registered")
    wallet = {"id": uuid.uuid4().hex, **w.model_dump(), "balance_ghs": Decimal("0")}
    wallets[wallet["id"]] = wallet
    return show(wallet)


@app.get("/wallets/{wid}")
def get_wallet(wid: str):
    return show(find(wid))


@app.post("/wallets/{wid}/top-up")
def deposit(wid: str, m: MoneyIn):
    w = find(wid)
    w["balance_ghs"] += m.amount_ghs
    record(w, "deposit", m.amount_ghs)
    return show(w)


@app.post("/transfers")
def send(s: SendIn):
    a, b = find(s.sender_id), find(s.receiver_id)
    if a is b:
        raise HTTPException(422, "Cannot send to yourself")
    if a["balance_ghs"] < s.amount_ghs:
        raise HTTPException(422, "Insufficient balance")
    a["balance_ghs"] -= s.amount_ghs
    b["balance_ghs"] += s.amount_ghs
    record(a, "sent", s.amount_ghs)
    record(b, "received", s.amount_ghs)
    return {"status": "done", "amount_ghs": text(s.amount_ghs)}


@app.get("/wallets/{wid}/statement")
def statement(wid: str):
    find(wid)
    return list(reversed([e for e in entries if e["wallet_id"] == wid]))
