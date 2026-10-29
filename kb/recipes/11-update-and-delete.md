# Change part of a record (PATCH) and delete a record

Use when: the client wants to edit or remove something. For edits, accept only the fields being changed: a model where
every field is optional, then apply `model_dump(exclude_unset=True)` so fields that were not sent stay as they were.
Delete answers 204 with no body; both answer 404 for a missing record.

```python
from fastapi import FastAPI, HTTPException, Response
from sqlmodel import Field, Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    stock: int = 0


class ProductPatch(SQLModel):
    name: str | None = None
    stock: int | None = Field(default=None, ge=0)


SQLModel.metadata.create_all(engine)
app = FastAPI()


@app.post("/products", status_code=201)
def add(p: Product) -> Product:
    with Session(engine) as s:
        s.add(p)
        s.commit()
        s.refresh(p)
        return p


@app.patch("/products/{pid}")
def edit(pid: int, patch: ProductPatch) -> Product:
    with Session(engine) as s:
        p = s.get(Product, pid)
        if p is None:
            raise HTTPException(404, "No such product")
        p.sqlmodel_update(patch.model_dump(exclude_unset=True))
        s.add(p)
        s.commit()
        s.refresh(p)
        return p


@app.delete("/products/{pid}", status_code=204)
def remove(pid: int) -> Response:
    with Session(engine) as s:
        p = s.get(Product, pid)
        if p is None:
            raise HTTPException(404, "No such product")
        s.delete(p)
        s.commit()
    return Response(status_code=204)
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
p = c.post("/products", json={"name": "Rice", "stock": 5}).json()
assert c.patch(f"/products/{p['id']}", json={"stock": 2}).json() == {"id": p["id"], "name": "Rice", "stock": 2}
assert c.delete(f"/products/{p['id']}").status_code == 204
assert c.delete(f"/products/{p['id']}").status_code == 404
```
