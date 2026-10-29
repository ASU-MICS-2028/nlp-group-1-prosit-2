# Testing the backend with pytest and TestClient

Use when: writing tests for the app, or checking your own work before handing it over. `TestClient(app)` calls the app
without starting a server. Make each test create its own data and never depend on another test or on an empty database.
Test the rules the client gave: the happy path, every refusal (status code), and missing records (404).

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()
stock: dict[str, int] = {}


class Move(BaseModel):
    item: str = Field(min_length=1)
    qty: int = Field(gt=0)


@app.post("/in")
def add(m: Move) -> dict:
    stock[m.item] = stock.get(m.item, 0) + m.qty
    return {"item": m.item, "qty": stock[m.item]}


@app.post("/out")
def remove(m: Move) -> dict:
    if stock.get(m.item, 0) < m.qty:
        raise HTTPException(409, "Not enough in stock")
    stock[m.item] -= m.qty
    return {"item": m.item, "qty": stock[m.item]}
```

```python check
import uuid
from fastapi.testclient import TestClient

client = TestClient(app)


def new_item():  # each test uses a fresh name, so tests never share data
    return f"item-{uuid.uuid4().hex[:6]}"


def test_stock_goes_up_and_down():
    item = new_item()
    client.post("/in", json={"item": item, "qty": 5})
    assert client.post("/out", json={"item": item, "qty": 2}).json()["qty"] == 3


def test_cannot_take_more_than_there_is():
    item = new_item()
    client.post("/in", json={"item": item, "qty": 1})
    assert client.post("/out", json={"item": item, "qty": 2}).status_code == 409


def test_bad_input_is_refused():
    assert client.post("/in", json={"item": "", "qty": 1}).status_code == 422


for test in (test_stock_goes_up_and_down, test_cannot_take_more_than_there_is, test_bad_input_is_refused):
    test()  # pytest finds test_* functions by itself; this line only lets the recipe check run them
```
