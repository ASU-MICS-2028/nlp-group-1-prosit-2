from datetime import date, datetime, timezone
from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(title="Campus Lost and Found Board")


class ItemCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    location: str = Field(..., min_length=1, max_length=200)
    found_date: date


class ClaimRequest(BaseModel):
    owner_name: str = Field(..., min_length=1, max_length=200)


class Item(BaseModel):
    id: int
    description: str
    location: str
    found_date: date
    reported_at: datetime
    claimed: bool = False
    owner_name: Optional[str] = None
    claimed_at: Optional[datetime] = None


_items: Dict[int, Item] = {}
_next_id = 1
_lock = Lock()


def _clean(value: str, field: str) -> str:
    v = value.strip()
    if not v:
        raise HTTPException(status_code=422, detail=f"{field} must not be empty")
    return v


@app.post("/items", response_model=Item, status_code=201)
def report_item(payload: ItemCreate):
    global _next_id
    description = _clean(payload.description, "description")
    location = _clean(payload.location, "location")
    if payload.found_date > date.today():
        raise HTTPException(status_code=422, detail="found_date cannot be in the future")
    with _lock:
        item = Item(
            id=_next_id,
            description=description,
            location=location,
            found_date=payload.found_date,
            reported_at=datetime.now(timezone.utc),
        )
        _items[item.id] = item
        _next_id += 1
    return item


@app.get("/items", response_model=List[Item])
def list_items(claimed: Optional[bool] = Query(None, description="Filter by claimed status")):
    with _lock:
        items = sorted(_items.values(), key=lambda i: i.id)
    if claimed is not None:
        items = [i for i in items if i.claimed == claimed]
    return items


@app.get("/items/unclaimed", response_model=List[Item])
def list_unclaimed():
    with _lock:
        return [i for i in sorted(_items.values(), key=lambda i: i.id) if not i.claimed]


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    with _lock:
        item = _items.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/items/{item_id}/claim", response_model=Item)
def claim_item(item_id: int, payload: ClaimRequest):
    owner = _clean(payload.owner_name, "owner_name")
    with _lock:
        item = _items.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        if item.claimed:
            raise HTTPException(status_code=409, detail="Item has already been claimed")
        item.claimed = True
        item.owner_name = owner
        item.claimed_at = datetime.now(timezone.utc)
        return item
