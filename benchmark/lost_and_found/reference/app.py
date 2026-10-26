# Reference backend for lost_and_found: proves the hidden tests are right.
# Deliberately uses different names (what, found_at, found_on, collected, collected_by) to exercise ops.json translation.
from datetime import date

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
items = {}


class ItemIn(BaseModel):
    what: str
    found_at: str
    found_on: date


class ClaimIn(BaseModel):
    collected_by: str


def find(item_id):
    if item_id not in items:
        raise HTTPException(404, "No such item")
    return items[item_id]


@app.post("/board/items", status_code=201)
def report_item(i: ItemIn):
    item = {"id": len(items) + 1, **i.model_dump(), "collected": False, "collected_by": None}
    items[item["id"]] = item
    return item


@app.get("/board/items")
def list_items():
    return list(items.values())


@app.get("/board/waiting")
def list_unclaimed():
    return [i for i in items.values() if not i["collected"]]


@app.get("/board/items/{item_id}")
def get_item(item_id: int):
    return find(item_id)


@app.post("/board/items/{item_id}/claim")
def claim_item(item_id: int, c: ClaimIn):
    item = find(item_id)
    if item["collected"]:
        raise HTTPException(409, "Already claimed")
    item["collected"] = True
    item["collected_by"] = c.collected_by
    return item
