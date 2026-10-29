# Second correct backend for market_stock: other valid choices than reference/
# (text ids, 200 on create, 422 for overselling, other names and paths, low list under /reports).
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
stock = {}


class ProductIn(BaseModel):
    title: str
    units: int
    alert_level: int


class Change(BaseModel):
    amount: int


def lookup(code):
    if code not in stock:
        raise HTTPException(404, "Unknown product")
    return stock[code]


def positive(n):
    if n <= 0:
        raise HTTPException(422, "Amount must be more than zero")


@app.post("/stock")
def add_product(p: ProductIn):
    if p.units < 0 or p.alert_level < 0:
        raise HTTPException(422, "Numbers cannot be negative")
    product = {"code": uuid4().hex, **p.model_dump()}
    stock[product["code"]] = product
    return product


@app.get("/stock")
def all_products():
    return list(stock.values())


@app.get("/stock/{code}")
def one_product(code: str):
    return lookup(code)


@app.post("/stock/{code}/sell")
def sell(code: str, c: Change):
    product = lookup(code)
    positive(c.amount)
    if c.amount > product["units"]:
        raise HTTPException(422, "Not enough in stock")
    product["units"] -= c.amount
    return product


@app.post("/stock/{code}/restock")
def restock(code: str, c: Change):
    product = lookup(code)
    positive(c.amount)
    product["units"] += c.amount
    return product


@app.get("/reports/low-stock")
def low_stock():
    return [p for p in stock.values() if p["units"] <= p["alert_level"]]
