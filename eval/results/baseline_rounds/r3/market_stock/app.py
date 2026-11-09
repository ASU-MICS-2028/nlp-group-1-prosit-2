from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, StrictInt, field_validator

app = FastAPI(title="Makola Provisions Stock Tracker")

_lock = Lock()
_items: Dict[int, dict] = {}
_next_id = 1


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    quantity: StrictInt = Field(0, ge=0)
    low_level: StrictInt = Field(0, ge=0)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    low_level: Optional[StrictInt] = Field(None, ge=0)

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
    amount: StrictInt = Field(..., gt=0)


class Item(BaseModel):
    id: int
    name: str
    quantity: int
    low_level: int
    is_low: bool


def _out(item: dict) -> dict:
    return {**item, "is_low": item["quantity"] <= item["low_level"]}


def _get(item_id: int) -> dict:
    item = _items.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _name_taken(name: str, exclude_id: Optional[int] = None) -> bool:
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
        return [_out(i) for i in sorted(_items.values(), key=lambda x: x["id"])]


@app.get("/items/low", response_model=List[Item])
def low_items():
    with _lock:
        return [_out(i) for i in sorted(_items.values(), key=lambda x: x["id"]) if i["quantity"] <= i["low_level"]]


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
                status_code=400,
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
