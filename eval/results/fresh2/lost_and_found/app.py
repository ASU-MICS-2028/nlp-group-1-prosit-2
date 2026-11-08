from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///lost_and_found.db", connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    location: str
    found_date: date
    claimed: bool = False
    owner_name: Optional[str] = None


class ItemCreate(BaseModel):
    description: str
    location: str
    found_date: date

    @field_validator("description", "location")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class ClaimRequest(BaseModel):
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


app = FastAPI(title="Lost and Found Board", lifespan=lifespan)


@app.post("/items", status_code=201, response_model=Item)
def report_item(data: ItemCreate):
    with Session(engine) as session:
        item = Item(**data.model_dump())
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.get("/items", response_model=list[Item])
def list_items():
    with Session(engine) as session:
        return session.exec(select(Item).order_by(Item.id)).all()


@app.get("/items/unclaimed", response_model=list[Item])
def list_unclaimed():
    with Session(engine) as session:
        return session.exec(select(Item).where(Item.claimed == False).order_by(Item.id)).all()  # noqa: E712


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    with Session(engine) as session:
        item = session.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        return item


@app.post("/items/{item_id}/claim", response_model=Item)
def claim_item(item_id: int, data: ClaimRequest):
    with Session(engine) as session:
        item = session.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        if item.claimed:
            raise HTTPException(409, "Item has already been claimed")
        item.claimed = True
        item.owner_name = data.owner_name
        session.add(item)
        session.commit()
        session.refresh(item)
        return item
