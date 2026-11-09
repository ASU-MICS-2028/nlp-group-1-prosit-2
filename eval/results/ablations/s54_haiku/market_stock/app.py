from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./stock.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str
    quantity: float
    low_level: float


class ItemCreate(BaseModel):
    name: str = Field(min_length=1)
    quantity: float = Field(ge=0, allow_inf_nan=False)
    low_level: float = Field(ge=0, allow_inf_nan=False)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class Amount(BaseModel):
    amount: float = Field(gt=0, allow_inf_nan=False)


@asynccontextmanager
async def lifespan(_: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Provisions stock", lifespan=lifespan)


def clean_number(value: float) -> float:
    return round(value, 6)


def get_item_or_404(session: Session, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/items", status_code=201)
def create_item(data: ItemCreate):
    item = Item(
        name=data.name,
        quantity=clean_number(data.quantity),
        low_level=clean_number(data.low_level),
    )
    with Session(engine) as session:
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.get("/items")
def list_items():
    with Session(engine) as session:
        return session.exec(select(Item).order_by(Item.id)).all()


@app.get("/items/low-stock")
def low_stock_items():
    with Session(engine) as session:
        items = session.exec(select(Item).order_by(Item.id)).all()
        return [item for item in items if item.quantity <= item.low_level]


@app.get("/items/{item_id}")
def get_item(item_id: int):
    with Session(engine) as session:
        return get_item_or_404(session, item_id)


@app.post("/items/{item_id}/sell")
def sell_item(item_id: int, data: Amount):
    with Session(engine) as session:
        item = get_item_or_404(session, item_id)
        if data.amount > item.quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot sell {data.amount}; only {item.quantity} in stock",
            )
        item.quantity = clean_number(item.quantity - data.amount)
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.post("/items/{item_id}/restock")
def restock_item(item_id: int, data: Amount):
    with Session(engine) as session:
        item = get_item_or_404(session, item_id)
        item.quantity = clean_number(item.quantity + data.amount)
        session.add(item)
        session.commit()
        session.refresh(item)
        return item
