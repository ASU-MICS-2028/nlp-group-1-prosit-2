from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///stock.db", connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    quantity: int
    low_level: int


class ItemCreate(BaseModel):
    name: str
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


app = FastAPI(lifespan=lifespan)


def get_item_or_404(session: Session, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/items", status_code=201, response_model=Item)
def create_item(data: ItemCreate):
    with Session(engine) as session:
        item = Item(name=data.name, quantity=data.quantity, low_level=data.low_level)
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
        return get_item_or_404(session, item_id)


@app.post("/items/{item_id}/sell", response_model=Item)
def sell_item(item_id: int, data: Amount):
    with Session(engine) as session:
        item = get_item_or_404(session, item_id)
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
def restock_item(item_id: int, data: Amount):
    with Session(engine) as session:
        item = get_item_or_404(session, item_id)
        item.quantity += data.amount
        session.add(item)
        session.commit()
        session.refresh(item)
        return item
