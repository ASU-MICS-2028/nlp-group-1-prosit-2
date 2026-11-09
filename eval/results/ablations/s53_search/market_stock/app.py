import threading
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///stock.db", connect_args={"check_same_thread": False})
stock_lock = threading.Lock()


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    quantity: int
    low_level: int


class ItemCreate(BaseModel):
    name: str = PField(min_length=1)
    quantity: int = PField(ge=0)
    low_level: int = PField(ge=0)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class Amount(BaseModel):
    amount: int = PField(gt=0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Makola Stock", lifespan=lifespan)


@app.post("/items", response_model=Item, status_code=201)
def create_item(data: ItemCreate):
    with Session(engine) as session:
        item = Item(**data.model_dump())
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.get("/items", response_model=List[Item])
def list_items():
    with Session(engine) as session:
        return session.exec(select(Item).order_by(Item.id)).all()


@app.get("/items/low", response_model=List[Item])
def low_items():
    with Session(engine) as session:
        return session.exec(
            select(Item).where(Item.quantity <= Item.low_level).order_by(Item.id)
        ).all()


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    with Session(engine) as session:
        item = session.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        return item


@app.post("/items/{item_id}/sell", response_model=Item)
def sell(item_id: int, data: Amount):
    with stock_lock, Session(engine) as session:
        item = session.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        if data.amount > item.quantity:
            raise HTTPException(
                409, f"Cannot sell {data.amount}; only {item.quantity} in stock"
            )
        item.quantity -= data.amount
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.post("/items/{item_id}/restock", response_model=Item)
def restock(item_id: int, data: Amount):
    with stock_lock, Session(engine) as session:
        item = session.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        item.quantity += data.amount
        session.add(item)
        session.commit()
        session.refresh(item)
        return item
