# MUTANT restock_not_saved: restock returns the new quantity but does not store it
# Reference backend for market_stock: proves the hidden tests are right.
# Deliberately uses different names (label, on_hand, reorder_at, count, /goods) to exercise ops.json translation.
from itertools import count

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()
goods = {}
ids = count(1)


class GoodIn(BaseModel):
    label: str
    on_hand: int = Field(ge=0)
    reorder_at: int = Field(ge=0)


class Movement(BaseModel):
    count: int = Field(gt=0)


def find(good_id):
    if good_id not in goods:
        raise HTTPException(404, "No such item")
    return goods[good_id]


@app.post("/goods", status_code=201)
def create_good(g: GoodIn):
    good = {"id": next(ids), **g.model_dump()}
    goods[good["id"]] = good
    return good


@app.get("/goods")
def list_goods():
    return list(goods.values())


@app.get("/goods/low")
def low_goods():
    return [g for g in goods.values() if g["on_hand"] <= g["reorder_at"]]


@app.get("/goods/{good_id}")
def get_good(good_id: int):
    return find(good_id)


@app.post("/goods/{good_id}/sales")
def sell(good_id: int, m: Movement):
    good = find(good_id)
    if m.count > good["on_hand"]:
        raise HTTPException(400, "Not enough in stock")
    good["on_hand"] -= m.count
    return good


@app.post("/goods/{good_id}/restocks")
def restock(good_id: int, m: Movement):
    good = find(good_id)
    return {**good, "on_hand": good["on_hand"] + m.count}
