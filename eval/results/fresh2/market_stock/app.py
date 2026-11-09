from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///stock.db", connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str
    quantity: int
    low_level: int


class ItemCreate(BaseModel):
    name: str = Field(min_length=1)
    quantity: int = Field(ge=0)
    low_level: int = Field(ge=0)


class AmountIn(BaseModel):
    amount: int = Field(gt=0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Makola Stock", lifespan=lifespan)


def get_item(session: Session, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/items", response_model=Item, status_code=201)
def create_item(data: ItemCreate):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name must not be empty")
    with Session(engine) as session:
        item = Item(name=name, quantity=data.quantity, low_level=data.low_level)
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.get("/items", response_model=List[Item])
def list_items():
    with Session(engine) as session:
        return session.exec(select(Item).order_by(Item.id)).all()


@app.get("/items/low-stock", response_model=List[Item])
def low_stock():
    with Session(engine) as session:
        return session.exec(
            select(Item).where(Item.quantity <= Item.low_level).order_by(Item.id)
        ).all()


@app.get("/items/{item_id}", response_model=Item)
def read_item(item_id: int):
    with Session(engine) as session:
        return get_item(session, item_id)


@app.post("/items/{item_id}/sell", response_model=Item)
def sell(item_id: int, data: AmountIn):
    with Session(engine) as session:
        item = get_item(session, item_id)
        if data.amount > item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot sell {data.amount}; only {item.quantity} in stock",
            )
        item.quantity -= data.amount
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.post("/items/{item_id}/restock", response_model=Item)
def restock(item_id: int, data: AmountIn):
    with Session(engine) as session:
        item = get_item(session, item_id)
        item.quantity += data.amount
        session.add(item)
        session.commit()
        session.refresh(item)
        return item
