# Keeping a group of values (an object, a list) in a table

Use when: a record has a group of values, such as sizes, an address or a list of tags, and SQLModel says
"<class 'dict'> has no matching SQLAlchemy type" or "<class 'list'> has no matching SQLAlchemy type".
Two ways:
- Separate columns (best when the parts are fixed and you filter on them): `length`, `width`, `height`.
- One JSON column (best when the parts vary): `Field(default_factory=dict, sa_column=Column(JSON))`.
Accept and return the nested shape the client uses in either case.

```python
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import JSON, Column
from sqlmodel import Field, Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Size(BaseModel):
    length: float
    width: float


class BoxIn(BaseModel):
    label: str
    size: Size  # nested in the request
    tags: list[str] = []


class Box(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    label: str
    length: float  # way 1: one column per part
    width: float
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))  # way 2: a JSON column


SQLModel.metadata.create_all(engine)
app = FastAPI()


def out(b: Box) -> dict:
    return {"id": b.id, "label": b.label, "size": {"length": b.length, "width": b.width}, "tags": b.tags}


@app.post("/boxes", status_code=201)
def add(body: BoxIn) -> dict:
    with Session(engine) as s:
        b = Box(label=body.label, length=body.size.length, width=body.size.width, tags=body.tags)
        s.add(b)
        s.commit()
        s.refresh(b)
        return out(b)


@app.get("/boxes/{bid}")
def get(bid: int) -> dict:
    with Session(engine) as s:
        return out(s.get(Box, bid))
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
b = c.post("/boxes", json={"label": "Books", "size": {"length": 40, "width": 30}, "tags": ["heavy"]}).json()
assert c.get(f"/boxes/{b['id']}").json() == {"id": b["id"], "label": "Books", "size": {"length": 40.0, "width": 30.0}, "tags": ["heavy"]}
```
