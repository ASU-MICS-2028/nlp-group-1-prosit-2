from threading import Lock
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Makola Provisions Stock Tracker")

_lock = Lock()
_items: Dict[int, dict] = {}
_next_id = 1


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    quantity: int = Field(..., ge=0, strict=True)
    low_level: int = Field(..., ge=0, strict=True)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class ItemUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    low_level: int | None = Field(None, ge=0, strict=True)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class Movement(BaseModel):
    amount: int = Field(..., gt=0, strict=True)


class Item(BaseModel):
    id: int
    name: str
    quantity: int
    low_level: int
    is_low: bool


def _out(d: dict) -> dict:
    return {**d, "is_low": d["quantity"] <= d["low_level"]}


def _get(item_id: int) -> dict:
    item = _items.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _name_taken(name: str, exclude_id: int | None = None) -> bool:
    low = name.lower()
    return any(i["name"].lower() == low and i["id"] != exclude_id for i in _items.values())


@app.post("/items", response_model=Item, status_code=201)
def create_item(data: ItemCreate):
    global _next_id
    with _lock:
        if _name_taken(data.name):
            raise HTTPException(status_code=409, detail="An item with this name already exists")
        item = {"id": _next_id, "name": data.name, "quantity": data.quantity, "low_level": data.low_level}
        _items[_next_id] = item
        _next_id += 1
        return _out(item)


@app.get("/items", response_model=List[Item])
def list_items():
    with _lock:
        return [_out(i) for i in _items.values()]


@app.get("/items/low-stock", response_model=List[Item])
def low_stock():
    with _lock:
        return [_out(i) for i in _items.values() if i["quantity"] <= i["low_level"]]


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    with _lock:
        return _out(_get(item_id))


@app.patch("/items/{item_id}", response_model=Item)
def update_item(item_id: int, data: ItemUpdate):
    with _lock:
        item = _get(item_id)
        if data.name is not None:
            if _name_taken(data.name, exclude_id=item_id):
                raise HTTPException(status_code=409, detail="An item with this name already exists")
            item["name"] = data.name
        if data.low_level is not None:
            item["low_level"] = data.low_level
        return _out(item)


@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    with _lock:
        _get(item_id)
        del _items[item_id]
        return {"deleted": item_id}


@app.post("/items/{item_id}/sell", response_model=Item)
def sell_item(item_id: int, data: Movement):
    with _lock:
        item = _get(item_id)
        if data.amount > item["quantity"]:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot sell {data.amount}; only {item['quantity']} in stock",
            )
        item["quantity"] -= data.amount
        return _out(item)


@app.post("/items/{item_id}/restock", response_model=Item)
def restock_item(item_id: int, data: Movement):
    with _lock:
        item = _get(item_id)
        item["quantity"] += data.amount
        return _out(item)
