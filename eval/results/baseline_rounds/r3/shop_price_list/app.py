from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, field_validator
from sqlmodel import SQLModel, Field, Session, create_engine, select

DATABASE_URL = "sqlite:///./price_list.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    name_key: str = Field(index=True, unique=True)
    price_pesewas: int


class ItemCreate(BaseModel):
    name: str
    price: float

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Name cannot be empty")
        if len(v) > 100:
            raise ValueError("Name is too long (max 100 characters)")
        return v

    @field_validator("price")
    @classmethod
    def check_price(cls, v: float) -> float:
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("Price must be a real number")
        if v <= 0:
            raise ValueError("Price must be more than zero")
        if v > 10_000_000:
            raise ValueError("Price is too large")
        if abs(round(v * 100) - v * 100) > 1e-6:
            raise ValueError("Price can have at most 2 decimal places (pesewas)")
        return v


class ItemOut(BaseModel):
    id: int
    name: str
    price: float
    currency: str = "GHS"


def to_out(item: Item) -> ItemOut:
    return ItemOut(id=item.id, name=item.name, price=item.price_pesewas / 100)


def get_session():
    with Session(engine) as session:
        yield session


app = FastAPI(title="Madina Provisions Shop - Price List")


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


SQLModel.metadata.create_all(engine)


@app.get("/")
def home():
    return {"message": "Price list is running. See /docs to use it."}


@app.post("/items", response_model=ItemOut, status_code=201)
def add_item(data: ItemCreate, session: Session = Depends(get_session)):
    key = data.name.lower()
    existing = session.exec(select(Item).where(Item.name_key == key)).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"'{existing.name}' is already on the price list")
    item = Item(name=data.name, name_key=key, price_pesewas=int(round(data.price * 100)))
    session.add(item)
    session.commit()
    session.refresh(item)
    return to_out(item)


@app.get("/items", response_model=List[ItemOut])
def list_items(session: Session = Depends(get_session)):
    items = session.exec(select(Item).order_by(Item.name_key)).all()
    return [to_out(i) for i in items]


@app.get("/items/by-name/{name}", response_model=ItemOut)
def get_item_by_name(name: str, session: Session = Depends(get_session)):
    key = " ".join(name.split()).lower()
    item = session.exec(select(Item).where(Item.name_key == key)).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"'{name}' is not on the price list")
    return to_out(item)


@app.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return to_out(item)


@app.delete("/items/{item_id}")
def remove_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    name = item.name
    session.delete(item)
    session.commit()
    return {"message": f"'{name}' has been taken off the price list", "id": item_id}
