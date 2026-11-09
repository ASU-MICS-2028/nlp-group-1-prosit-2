from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Makola Provisions Stock Tracker")


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    quantity: int = Field(0, ge=0)
    low_level: int = Field(0, ge=0)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    low_level: Optional[int] = Field(None, ge=0)

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
    amount: int = Field(..., gt=0, description="Must be more than zero")


class Item(BaseModel):
    id: int
    name: str
    quantity: int
    low_level: int
    is_low: bool


_items: Dict[int, dict] = {}
_next_id = 1
_lock = Lock()


def _out(d: dict) -> Item:
    return Item(id=d["id"], name=d["name"], quantity=d["quantity"], low_level=d["low_level"], is_low=d["quantity"] <= d["low_level"])


def _get(item_id: int) -> dict:
    d = _items.get(item_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return d


def _name_taken(name: str, exclude_id: Optional[int] = None) -> bool:
    low = name.lower()
    return any(d["name"].lower() == low and d["id"] != exclude_id for d in _items.values())


@app.post("/items", response_model=Item, status_code=201)
def create_item(data: ItemCreate):
    global _next_id
    with _lock:
        if _name_taken(data.name):
            raise HTTPException(status_code=409, detail="An item with this name already exists")
        d = {"id": _next_id, "name": data.name, "quantity": data.quantity, "low_level": data.low_level}
        _items[_next_id] = d
        _next_id += 1
        return _out(d)


@app.get("/items", response_model=List[Item])
def list_items():
    return [_out(d) for d in sorted(_items.values(), key=lambda x: x["id"])]


@app.get("/items/low", response_model=List[Item])
def low_items():
    return [_out(d) for d in sorted(_items.values(), key=lambda x: x["id"]) if d["quantity"] <= d["low_level"]]


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    return _out(_get(item_id))


@app.patch("/items/{item_id}", response_model=Item)
def update_item(item_id: int, data: ItemUpdate):
    with _lock:
        d = _get(item_id)
        if data.name is not None:
            if _name_taken(data.name, exclude_id=item_id):
                raise HTTPException(status_code=409, detail="An item with this name already exists")
            d["name"] = data.name
        if data.low_level is not None:
            d["low_level"] = data.low_level
        return _out(d)


@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    with _lock:
        _get(item_id)
        del _items[item_id]
        return {"deleted": item_id}


@app.post("/items/{item_id}/sell", response_model=Item)
def sell_item(item_id: int, data: Movement):
    with _lock:
        d = _get(item_id)
        if data.amount > d["quantity"]:
            raise HTTPException(status_code=409, detail=f"Cannot sell {data.amount}; only {d['quantity']} in stock")
        d["quantity"] -= data.amount
        return _out(d)


@app.post("/items/{item_id}/restock", response_model=Item)
def restock_item(item_id: int, data: Movement):
    with _lock:
        d = _get(item_id)
        d["quantity"] += data.amount
        return _out(d)
