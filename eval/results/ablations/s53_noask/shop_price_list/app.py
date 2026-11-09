from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///shop.db", connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    price: float


class ItemIn(BaseModel):
    name: str = PField(min_length=1)
    price: float = PField(ge=0)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Provisions Shop Price List", lifespan=lifespan)


@app.post("/items", response_model=Item, status_code=201)
def add_item(data: ItemIn):
    with Session(engine) as s:
        item = Item(name=data.name, price=data.price)
        s.add(item)
        s.commit()
        s.refresh(item)
        return item


@app.get("/items", response_model=List[Item])
def list_items():
    with Session(engine) as s:
        return s.exec(select(Item).order_by(Item.name)).all()


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    with Session(engine) as s:
        item = s.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        return item


@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    with Session(engine) as s:
        item = s.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        s.delete(item)
        s.commit()
        return {"deleted": item_id}
