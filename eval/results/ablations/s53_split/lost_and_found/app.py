from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///lost_and_found.db", connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    found_where: str
    found_on: date
    status: str = "waiting"
    owner_name: Optional[str] = None


class ItemCreate(BaseModel):
    description: str
    found_where: str
    found_on: date

    @field_validator("description", "found_where")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class ClaimIn(BaseModel):
    owner_name: str

    @field_validator("owner_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Campus Lost and Found", lifespan=lifespan)


def get_item_or_404(session: Session, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/items", response_model=Item, status_code=201)
def report_item(data: ItemCreate):
    with Session(engine) as session:
        item = Item(description=data.description, found_where=data.found_where, found_on=data.found_on)
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.get("/items", response_model=List[Item])
def list_items():
    with Session(engine) as session:
        return session.exec(select(Item).order_by(Item.id)).all()


@app.get("/items/waiting", response_model=List[Item])
def list_waiting():
    with Session(engine) as session:
        return session.exec(select(Item).where(Item.status == "waiting").order_by(Item.id)).all()


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    with Session(engine) as session:
        return get_item_or_404(session, item_id)


@app.post("/items/{item_id}/claim", response_model=Item)
def claim_item(item_id: int, data: ClaimIn):
    with Session(engine) as session:
        item = get_item_or_404(session, item_id)
        if item.status == "claimed":
            raise HTTPException(status_code=409, detail="Item has already been claimed")
        item.status = "claimed"
        item.owner_name = data.owner_name
        session.add(item)
        session.commit()
        session.refresh(item)
        return item
