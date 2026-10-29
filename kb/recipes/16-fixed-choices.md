# A field with fixed choices (status, category, size, type)

Use when: a value must be one of a known list: a status (pending, paid), a size (small, medium, large), a category.
Use a `str` Enum: FastAPI refuses anything else with 422 and lists the allowed values in the API docs. Filtering a
list by the choice comes for free.

```python
from enum import Enum

from fastapi import FastAPI
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Size(str, Enum):
    small = "small"
    medium = "medium"
    large = "large"


class ShirtIn(SQLModel):
    colour: str
    size: Size


class Shirt(ShirtIn, table=True):
    id: int | None = Field(default=None, primary_key=True)


SQLModel.metadata.create_all(engine)
app = FastAPI()


@app.post("/shirts", status_code=201)
def add(body: ShirtIn) -> Shirt:
    with Session(engine) as s:
        row = Shirt.model_validate(body)
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


@app.get("/shirts")
def shirts(size: Size | None = None) -> list[Shirt]:
    q = select(Shirt) if size is None else select(Shirt).where(Shirt.size == size)
    with Session(engine) as s:
        return s.exec(q).all()
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
assert c.post("/shirts", json={"colour": "red", "size": "large"}).status_code == 201
assert c.post("/shirts", json={"colour": "blue", "size": "huge"}).status_code == 422
assert len(c.get("/shirts", params={"size": "large"}).json()) == 1
assert c.get("/shirts", params={"size": "small"}).json() == []
```
