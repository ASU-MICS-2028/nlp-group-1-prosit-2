from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, func, select

engine = create_engine("sqlite:///shop.db", connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    price: float


class ItemIn(BaseModel):
    name: str
    price: float = PField(ge=0, allow_inf_nan=False)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("The item must have a name.")
        return v

    @field_validator("price", mode="before")
    @classmethod
    def price_is_number(cls, v):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError("The price must be a number.")
        return v


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Shop price list", lifespan=lifespan)


def to_dict(item: Item) -> dict:
    return {"name": item.name, "price": item.price}


def find(session: Session, name: str) -> Optional[Item]:
    return session.exec(
        select(Item).where(func.lower(Item.name) == name.strip().lower())
    ).first()


@app.post("/items", status_code=201)
def add_item(data: ItemIn):
    with Session(engine) as session:
        if find(session, data.name):
            raise HTTPException(409, f"'{data.name}' is already on the list.")
        item = Item(name=data.name, price=data.price)
        session.add(item)
        session.commit()
        session.refresh(item)
        return to_dict(item)


@app.get("/items")
def list_items():
    with Session(engine) as session:
        items = session.exec(select(Item).order_by(func.lower(Item.name))).all()
        return [to_dict(i) for i in items]


@app.get("/items/{name}")
def get_item(name: str):
    with Session(engine) as session:
        item = find(session, name)
        if not item:
            raise HTTPException(404, f"'{name}' was not found on the list.")
        return to_dict(item)


@app.delete("/items/{name}")
def delete_item(name: str):
    with Session(engine) as session:
        item = find(session, name)
        if not item:
            raise HTTPException(404, f"'{name}' was not found on the list.")
        result = to_dict(item)
        session.delete(item)
        session.commit()
        return {"message": f"'{item.name}' was taken off the list.", "item": result}
