# MUTANT negative_transfer_allowed: '    target: int\n    value: Decimal\n' instead of '    target: int\n    value: Money\n'
# Reference backend for momo_wallet: proves the hidden tests are right.
# Deliberately uses different names (holder, msisdn, available, value, source, target, /momo/...) to exercise ops.json.
# Money is kept as Decimal so that 0.70 + 0.10 is exactly 0.80.
from decimal import Decimal
from typing import Annotated

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()
accounts, history = {}, []
Money = Annotated[Decimal, Field(gt=0, decimal_places=2)]


class AccountIn(BaseModel):
    holder: str
    msisdn: str


class DepositIn(BaseModel):
    value: Money


class TransferIn(BaseModel):
    source: int
    target: int
    value: Decimal


def find(aid):
    if aid not in accounts:
        raise HTTPException(404, "No such wallet")
    return accounts[aid]


def show(a):
    return {**a, "available": float(a["available"])}


def log(a, value):
    history.append({"account": a["id"], "value": float(value), "running_balance": float(a["available"])})


@app.post("/momo/accounts", status_code=201)
def open_wallet(a: AccountIn):
    if any(x["msisdn"] == a.msisdn for x in accounts.values()):
        raise HTTPException(409, "This phone number already has a wallet")
    acc = {"id": len(accounts) + 1, **a.model_dump(), "available": Decimal(0)}
    accounts[acc["id"]] = acc
    return show(acc)


@app.get("/momo/accounts/{aid}")
def get_wallet(aid: int):
    return show(find(aid))


@app.post("/momo/accounts/{aid}/deposits", status_code=201)
def deposit(aid: int, d: DepositIn):
    acc = find(aid)
    acc["available"] += d.value
    log(acc, d.value)
    return show(acc)


@app.post("/momo/transfers", status_code=201)
def transfer(t: TransferIn):
    src, dst = find(t.source), find(t.target)
    if src is dst:
        raise HTTPException(400, "Cannot send money to the same wallet")
    if src["available"] < t.value:
        raise HTTPException(400, "Not enough money in the wallet")
    src["available"] -= t.value
    dst["available"] += t.value
    log(src, t.value)
    log(dst, t.value)
    return {"source": src["id"], "target": dst["id"], "value": float(t.value)}


@app.get("/momo/accounts/{aid}/history")
def list_history(aid: int):
    find(aid)
    return [h for h in history if h["account"] == aid]
