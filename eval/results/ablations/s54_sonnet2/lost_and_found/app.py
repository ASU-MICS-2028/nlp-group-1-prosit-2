from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///lostfound.db", connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    location: str
    date_found: date
    claimed: bool = False
    owner_name: Optional[str] = None


class ItemIn(BaseModel):
    description: str
    location: str
    date_found: date

    @field_validator("description", "location")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class ClaimIn(BaseModel):
    owner_name: str

    @field_validator("owner_name")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


SQLModel.metadata.create_all(engine)
app = FastAPI()


def get_or_404(s, item_id):
    item = s.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    return item


@app.post("/items", status_code=201)
def create_item(data: ItemIn):
    with Session(engine) as s:
        item = Item(**data.model_dump())
        s.add(item)
        s.commit()
        s.refresh(item)
        return item


@app.get("/items")
def list_items():
    with Session(engine) as s:
        return s.exec(select(Item).order_by(Item.id)).all()


@app.get("/items/unclaimed")
def list_unclaimed():
    with Session(engine) as s:
        return s.exec(select(Item).where(Item.claimed == False).order_by(Item.id)).all()  # noqa: E712


@app.get("/items/{item_id}")
def get_item(item_id: int):
    with Session(engine) as s:
        return get_or_404(s, item_id)


@app.post("/items/{item_id}/claim")
def claim_item(item_id: int, data: ClaimIn):
    with Session(engine) as s:
        item = get_or_404(s, item_id)
        if item.claimed:
            raise HTTPException(409, "Item already claimed")
        item.claimed = True
        item.owner_name = data.owner_name
        s.add(item)
        s.commit()
        s.refresh(item)
        return item
