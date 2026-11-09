from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./shop.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    price: float


def check_price(v):
    if v is None:
        return v
    if v <= 0:
        raise ValueError("price must be greater than zero")
    if round(v, 2) != v:
        raise ValueError("price can have at most 2 decimal places (pesewas, e.g. 12.50)")
    return v


def clean_name(v):
    if v is None:
        return v
    v = v.strip()
    if not v:
        raise ValueError("name must not be empty")
    return v


class ItemCreate(BaseModel):
    name: str
    price: float

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v):
        return clean_name(v)

    @field_validator("price")
    @classmethod
    def _validate_price(cls, v):
        return check_price(v)


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v):
        return clean_name(v)

    @field_validator("price")
    @classmethod
    def _validate_price(cls, v):
        return check_price(v)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Provisions Price List", lifespan=lifespan)


def get_item_or_404(session: Session, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/items", response_model=Item, status_code=201)
def add_item(data: ItemCreate):
    item = Item(name=data.name, price=data.price)
    with Session(engine) as session:
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.get("/items", response_model=list[Item])
def list_items():
    with Session(engine) as session:
        return session.exec(select(Item).order_by(Item.id)).all()


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    with Session(engine) as session:
        return get_item_or_404(session, item_id)


@app.patch("/items/{item_id}", response_model=Item)
def update_item(item_id: int, data: ItemUpdate):
    with Session(engine) as session:
        item = get_item_or_404(session, item_id)
        if data.name is not None:
            item.name = data.name
        if data.price is not None:
            item.price = data.price
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    with Session(engine) as session:
        item = get_item_or_404(session, item_id)
        session.delete(item)
        session.commit()
        return {"deleted": True, "id": item_id}
