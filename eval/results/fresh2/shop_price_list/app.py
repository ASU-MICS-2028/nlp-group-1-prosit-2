from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///shop.db", connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    price: float


class ItemCreate(BaseModel):
    name: str
    price: float = PField(ge=0)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class PriceUpdate(BaseModel):
    price: float = PField(ge=0)


app = FastAPI(title="Provisions Shop Price List")


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


def name_taken(session: Session, name: str) -> bool:
    for it in session.exec(select(Item)).all():
        if it.name.lower() == name.lower():
            return True
    return False


@app.post("/items", status_code=201, response_model=Item)
def add_item(data: ItemCreate):
    with Session(engine) as session:
        if name_taken(session, data.name):
            raise HTTPException(409, "An item with this name is already on the list")
        item = Item(name=data.name, price=data.price)
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.get("/items", response_model=List[Item])
def list_items():
    with Session(engine) as session:
        return session.exec(select(Item).order_by(Item.name)).all()


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    with Session(engine) as session:
        item = session.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        return item


@app.patch("/items/{item_id}", response_model=Item)
def change_price(item_id: int, data: PriceUpdate):
    with Session(engine) as session:
        item = session.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        item.price = data.price
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.delete("/items/{item_id}")
def remove_item(item_id: int):
    with Session(engine) as session:
        item = session.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        session.delete(item)
        session.commit()
        return {"deleted": item_id}
