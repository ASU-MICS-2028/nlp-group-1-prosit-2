from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///shop.db", connect_args={"check_same_thread": False})


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    price: float


class ItemCreate(SQLModel):
    name: str
    price: float = Field(gt=0)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class PriceUpdate(SQLModel):
    price: float = Field(gt=0)


app = FastAPI(title="Provisions Shop Price List")


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


def find_item(session: Session, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/items", response_model=Item, status_code=201)
def add_item(data: ItemCreate, session: Session = Depends(get_session)):
    for existing in session.exec(select(Item)).all():
        if existing.name.lower() == data.name.lower():
            raise HTTPException(status_code=409, detail="An item with this name is already on the list")
    item = Item(name=data.name, price=data.price)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.get("/items", response_model=List[Item])
def list_items(session: Session = Depends(get_session)):
    return session.exec(select(Item).order_by(Item.name)).all()


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int, session: Session = Depends(get_session)):
    return find_item(session, item_id)


@app.patch("/items/{item_id}", response_model=Item)
def change_price(item_id: int, data: PriceUpdate, session: Session = Depends(get_session)):
    item = find_item(session, item_id)
    item.price = data.price
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.delete("/items/{item_id}")
def remove_item(item_id: int, session: Session = Depends(get_session)):
    item = find_item(session, item_id)
    session.delete(item)
    session.commit()
    return {"detail": "Item removed", "id": item_id}
