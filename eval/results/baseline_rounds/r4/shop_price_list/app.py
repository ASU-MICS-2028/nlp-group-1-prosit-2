from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import SQLModel, Field, Session, create_engine, select


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    name_key: str = Field(index=True, unique=True)
    price: float


class ItemCreate(BaseModel):
    name: str = PField(..., min_length=1, max_length=100)
    price: float = PField(..., gt=0, le=10_000_000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("name must not be empty")
        return v


class PriceUpdate(BaseModel):
    price: float = PField(..., gt=0, le=10_000_000)


class ItemOut(BaseModel):
    id: int
    name: str
    price: float


engine = create_engine("sqlite:///shop_prices.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)

app = FastAPI(title="Madina Provisions Shop Price List")


def get_session():
    with Session(engine) as session:
        yield session


def key_of(name: str) -> str:
    return " ".join(name.split()).lower()


def out(item: Item) -> ItemOut:
    return ItemOut(id=item.id, name=item.name, price=round(item.price, 2))


@app.get("/")
def home():
    return {"message": "Price list is running. See /docs to use it."}


@app.post("/items", response_model=ItemOut, status_code=201)
def add_item(data: ItemCreate, session: Session = Depends(get_session)):
    k = key_of(data.name)
    if session.exec(select(Item).where(Item.name_key == k)).first():
        raise HTTPException(status_code=409, detail=f"'{data.name}' is already on the price list")
    item = Item(name=data.name, name_key=k, price=round(data.price, 2))
    session.add(item)
    session.commit()
    session.refresh(item)
    return out(item)


@app.get("/items", response_model=List[ItemOut])
def list_items(session: Session = Depends(get_session)):
    items = session.exec(select(Item).order_by(Item.name_key)).all()
    return [out(i) for i in items]


@app.get("/items/by-name/{name}", response_model=ItemOut)
def get_by_name(name: str, session: Session = Depends(get_session)):
    item = session.exec(select(Item).where(Item.name_key == key_of(name))).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"'{name}' is not on the price list")
    return out(item)


@app.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return out(item)


@app.patch("/items/{item_id}", response_model=ItemOut)
def change_price(item_id: int, data: PriceUpdate, session: Session = Depends(get_session)):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.price = round(data.price, 2)
    session.add(item)
    session.commit()
    session.refresh(item)
    return out(item)


@app.delete("/items/{item_id}")
def remove_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    name = item.name
    session.delete(item)
    session.commit()
    return {"message": f"'{name}' has been taken off the price list", "id": item_id}


@app.delete("/items/by-name/{name}")
def remove_by_name(name: str, session: Session = Depends(get_session)):
    item = session.exec(select(Item).where(Item.name_key == key_of(name))).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"'{name}' is not on the price list")
    item_id, item_name = item.id, item.name
    session.delete(item)
    session.commit()
    return {"message": f"'{item_name}' has been taken off the price list", "id": item_id}
