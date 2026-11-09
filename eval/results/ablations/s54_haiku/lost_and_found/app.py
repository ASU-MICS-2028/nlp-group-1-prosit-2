from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./lost_and_found.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class ItemCreate(SQLModel):
    description: str = Field(min_length=1)
    found_location: str = Field(min_length=1)
    found_date: date


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    found_location: str
    found_date: date
    claimed: bool = False
    owner_name: Optional[str] = None


class ClaimIn(SQLModel):
    owner_name: str = Field(min_length=1)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


SQLModel.metadata.create_all(engine)

app = FastAPI(title="Lost and Found Board", lifespan=lifespan)


def _not_blank(value: str, field: str) -> None:
    if not value.strip():
        raise HTTPException(status_code=422, detail=f"{field} must not be blank")


@app.post("/items", status_code=201, response_model=Item)
def report_item(data: ItemCreate):
    _not_blank(data.description, "description")
    _not_blank(data.found_location, "found_location")
    item = Item(
        description=data.description.strip(),
        found_location=data.found_location.strip(),
        found_date=data.found_date,
    )
    with Session(engine) as session:
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@app.get("/items", response_model=List[Item])
def list_items():
    with Session(engine) as session:
        return session.exec(select(Item).order_by(Item.id)).all()


@app.get("/items/waiting", response_model=List[Item])
def list_waiting_items():
    with Session(engine) as session:
        return session.exec(
            select(Item).where(Item.claimed == False).order_by(Item.id)  # noqa: E712
        ).all()


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    with Session(engine) as session:
        item = session.get(Item, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        return item


@app.post("/items/{item_id}/claim", response_model=Item)
def claim_item(item_id: int, data: ClaimIn):
    _not_blank(data.owner_name, "owner_name")
    with Session(engine) as session:
        item = session.get(Item, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        if item.claimed:
            raise HTTPException(status_code=409, detail="Item has already been claimed")
        item.claimed = True
        item.owner_name = data.owner_name.strip()
        session.add(item)
        session.commit()
        session.refresh(item)
        return item
