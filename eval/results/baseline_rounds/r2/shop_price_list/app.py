from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./price_list.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    name_key: str = Field(index=True, unique=True)
    price: float
    unit: Optional[str] = None


def clean_name(value: str) -> str:
    return " ".join(value.split())


class ItemCreate(BaseModel):
    name: str
    price: float
    unit: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_ok(cls, v: str) -> str:
        v = clean_name(v or "")
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 100:
            raise ValueError("name is too long (max 100 characters)")
        return v

    @field_validator("price")
    @classmethod
    def price_ok(cls, v: float) -> float:
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("price must be a real number")
        if v <= 0:
            raise ValueError("price must be greater than zero")
        if v > 1_000_000_000:
            raise ValueError("price is too large")
        return round(v, 2)

    @field_validator("unit")
    @classmethod
    def unit_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = clean_name(v)
        if len(v) > 50:
            raise ValueError("unit is too long (max 50 characters)")
        return v or None


class PriceUpdate(BaseModel):
    price: float

    @field_validator("price")
    @classmethod
    def price_ok(cls, v: float) -> float:
        return ItemCreate.price_ok(v)


class ItemOut(BaseModel):
    id: int
    name: str
    price: float
    unit: Optional[str] = None


def to_out(item: Item) -> ItemOut:
    return ItemOut(id=item.id, name=item.name, price=item.price, unit=item.unit)


app = FastAPI(title="Madina Provisions Shop - Price List")


@app.on_event("startup")
def on_startup() -> None:
    SQLModel.metadata.create_all(engine)


SQLModel.metadata.create_all(engine)


@app.get("/")
def home():
    return {
        "message": "Welcome to your shop price list",
        "how_to_use": {
            "add an item": "POST /items with name, price (and optional unit)",
            "see all items": "GET /items",
            "price of one item by number": "GET /items/{id}",
            "price of one item by name": "GET /items/lookup?name=Milo",
            "change a price": "PATCH /items/{id} with price",
            "remove an item": "DELETE /items/{id}",
        },
    }


@app.post("/items", response_model=ItemOut, status_code=201)
def add_item(data: ItemCreate):
    key = data.name.lower()
    with Session(engine) as session:
        existing = session.exec(select(Item).where(Item.name_key == key)).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"'{existing.name}' is already on the price list (id {existing.id}).",
            )
        item = Item(name=data.name, name_key=key, price=data.price, unit=data.unit)
        session.add(item)
        session.commit()
        session.refresh(item)
        return to_out(item)


@app.get("/items", response_model=List[ItemOut])
def list_items(search: Optional[str] = Query(default=None, description="Part of a name to filter by")):
    with Session(engine) as session:
        items = session.exec(select(Item)).all()
    if search:
        s = clean_name(search).lower()
        items = [i for i in items if s in i.name_key]
    items = sorted(items, key=lambda i: i.name_key)
    return [to_out(i) for i in items]


@app.get("/items/lookup", response_model=ItemOut)
def lookup_item(name: str = Query(..., description="Exact name of the item")):
    key = clean_name(name).lower()
    if not key:
        raise HTTPException(status_code=400, detail="Please give a name to look up.")
    with Session(engine) as session:
        item = session.exec(select(Item).where(Item.name_key == key)).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"'{clean_name(name)}' is not on the price list.")
    return to_out(item)


@app.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: int):
    with Session(engine) as session:
        item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"No item with id {item_id}.")
    return to_out(item)


@app.patch("/items/{item_id}", response_model=ItemOut)
def change_price(item_id: int, data: PriceUpdate):
    with Session(engine) as session:
        item = session.get(Item, item_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"No item with id {item_id}.")
        item.price = data.price
        session.add(item)
        session.commit()
        session.refresh(item)
        return to_out(item)


@app.delete("/items/{item_id}")
def remove_item(item_id: int):
    with Session(engine) as session:
        item = session.get(Item, item_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"No item with id {item_id}.")
        name = item.name
        session.delete(item)
        session.commit()
    return {"message": f"'{name}' has been removed from the price list.", "id": item_id}
