from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, update

engine = create_engine(
    "sqlite:///./lost_and_found.db", connect_args={"check_same_thread": False}
)


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    location: str
    found_date: date
    claimed: bool = Field(default=False, index=True)
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


app = FastAPI(title="Campus Lost and Found", lifespan=lifespan)


@app.post("/items", response_model=Item, status_code=201)
def report_item(data: ItemCreate):
    with Session(engine) as s:
        item = Item(**data.model_dump())
        s.add(item)
        s.commit()
        s.refresh(item)
        return item


@app.get("/items", response_model=List[Item])
def list_items():
    with Session(engine) as s:
        return s.exec(select(Item).order_by(Item.id)).all()


@app.get("/items/unclaimed", response_model=List[Item])
def list_unclaimed():
    with Session(engine) as s:
        return s.exec(select(Item).where(Item.claimed == False).order_by(Item.id)).all()  # noqa: E712


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    with Session(engine) as s:
        item = s.get(Item, item_id)
        if not item:
            raise HTTPException(404, "Item not found")
        return item


@app.post("/items/{item_id}/claim", response_model=Item)
def claim_item(item_id: int, data: ClaimRequest):
    with Session(engine) as s:
        if not s.get(Item, item_id):
            raise HTTPException(404, "Item not found")
        # Atomic: only succeeds if the item is still unclaimed
        result = s.exec(
            update(Item)
            .where(Item.id == item_id, Item.claimed == False)  # noqa: E712
            .values(claimed=True, owner_name=data.owner_name)
        )
        s.commit()
        if result.rowcount == 0:
            raise HTTPException(409, "Item has already been claimed")
        item = s.get(Item, item_id)
        s.refresh(item)
        return item
