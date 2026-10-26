# MUTANT update_not_saved: update returns the new fare but does not store it
# Reference backend for trotro_fares: proves the hidden tests are right.
# Deliberately uses different names (start, end, price, /lines) to exercise ops.json translation.
from itertools import count

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
lines = {}
ids = count(1)


class LineIn(BaseModel):
    start: str
    end: str
    price: float


class PriceIn(BaseModel):
    price: float


def between(a, b):
    for line in lines.values():
        if {line["start"], line["end"]} == {a, b}:
            return line
    return None


@app.post("/lines", status_code=201)
def create_line(l: LineIn):
    if l.price <= 0:
        raise HTTPException(400, "Fare must be more than zero")
    if between(l.start, l.end):
        raise HTTPException(409, "That route already exists")
    line = {"id": next(ids), **l.model_dump()}
    lines[line["id"]] = line
    return line


@app.get("/lines")
def list_lines():
    return list(lines.values())


@app.get("/fare")
def find_fare(start: str, end: str):
    line = between(start, end)
    if line is None:
        raise HTTPException(404, "No route between those stops")
    return line


@app.patch("/lines/{line_id}")
def update_price(line_id: int, p: PriceIn):
    if line_id not in lines:
        raise HTTPException(404, "No such route")
    if p.price <= 0:
        raise HTTPException(400, "Fare must be more than zero")
    return {**lines[line_id], "price": p.price}
