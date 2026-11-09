from datetime import date, datetime, timezone
from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Campus Lost and Found Board")

_items: Dict[int, dict] = {}
_next_id = 1
_lock = Lock()


class ItemCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    location_found: str = Field(..., min_length=1, max_length=200)
    date_found: date

    @field_validator("description", "location_found")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("date_found")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("date found cannot be in the future")
        return v


class ClaimRequest(BaseModel):
    owner_name: str = Field(..., min_length=1, max_length=200)

    @field_validator("owner_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class Item(BaseModel):
    id: int
    description: str
    location_found: str
    date_found: date
    reported_at: str
    claimed: bool
    owner_name: Optional[str] = None
    claimed_at: Optional[str] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_or_404(item_id: int) -> dict:
    item = _items.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.get("/")
def root():
    return {"message": "Campus lost-and-found board", "endpoints": [
        "POST /items", "GET /items", "GET /items/unclaimed", "GET /items/{id}", "POST /items/{id}/claim"]}


@app.post("/items", response_model=Item, status_code=201)
def report_item(payload: ItemCreate):
    global _next_id
    with _lock:
        item = {
            "id": _next_id,
            "description": payload.description,
            "location_found": payload.location_found,
            "date_found": payload.date_found,
            "reported_at": _now(),
            "claimed": False,
            "owner_name": None,
            "claimed_at": None,
        }
        _items[_next_id] = item
        _next_id += 1
        return item


@app.get("/items", response_model=List[Item])
def list_items(status: Optional[str] = Query(None, description="'unclaimed' or 'claimed'")):
    items = sorted(_items.values(), key=lambda i: i["id"])
    if status is None:
        return items
    s = status.lower()
    if s in ("unclaimed", "waiting", "open"):
        return [i for i in items if not i["claimed"]]
    if s == "claimed":
        return [i for i in items if i["claimed"]]
    raise HTTPException(status_code=400, detail="status must be 'unclaimed' or 'claimed'")


@app.get("/items/unclaimed", response_model=List[Item])
def list_unclaimed():
    return [i for i in sorted(_items.values(), key=lambda i: i["id"]) if not i["claimed"]]


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    return _get_or_404(item_id)


@app.post("/items/{item_id}/claim", response_model=Item)
def claim_item(item_id: int, payload: ClaimRequest):
    with _lock:
        item = _get_or_404(item_id)
        if item["claimed"]:
            raise HTTPException(status_code=409, detail="Item has already been claimed")
        item["claimed"] = True
        item["owner_name"] = payload.owner_name
        item["claimed_at"] = _now()
        return item
