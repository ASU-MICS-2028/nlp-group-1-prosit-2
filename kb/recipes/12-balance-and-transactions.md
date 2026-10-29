# A balance that changes with each transaction (wallet, savings, stock)

Use when: money or items come in and go out: deposits and withdrawals, contributions and payouts, stock in and stock out.
Save every movement as its own row (the history), compute the balance as the sum of the rows, and refuse a withdrawal
that would take the balance below zero (409). Amounts in whole pesewas (see the money recipe).

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField
from sqlmodel import Field, Session, SQLModel, create_engine, func, select
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Movement(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    owner: str = Field(index=True)
    amount: int  # pesewas: positive in, negative out


SQLModel.metadata.create_all(engine)
app = FastAPI()


class AmountIn(BaseModel):
    amount: int = PField(gt=0)


def balance(s: Session, owner: str) -> int:
    return s.exec(select(func.coalesce(func.sum(Movement.amount), 0)).where(Movement.owner == owner)).one()


@app.post("/wallets/{owner}/in", status_code=201)
def pay_in(owner: str, body: AmountIn) -> dict:
    with Session(engine) as s:
        s.add(Movement(owner=owner, amount=body.amount))
        s.commit()
        return {"owner": owner, "balance": balance(s, owner)}


@app.post("/wallets/{owner}/out", status_code=201)
def pay_out(owner: str, body: AmountIn) -> dict:
    with Session(engine) as s:
        if balance(s, owner) < body.amount:
            raise HTTPException(409, "Not enough money")
        s.add(Movement(owner=owner, amount=-body.amount))
        s.commit()
        return {"owner": owner, "balance": balance(s, owner)}


@app.get("/wallets/{owner}")
def show(owner: str) -> dict:
    with Session(engine) as s:
        history = s.exec(select(Movement).where(Movement.owner == owner).order_by(Movement.id)).all()
        return {"owner": owner, "balance": balance(s, owner), "history": [m.amount for m in history]}
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
c.post("/wallets/ama/in", json={"amount": 500})
assert c.post("/wallets/ama/out", json={"amount": 200}).json()["balance"] == 300
assert c.post("/wallets/ama/out", json={"amount": 301}).status_code == 409
assert c.get("/wallets/ama").json() == {"owner": "ama", "balance": 300, "history": [500, -200]}
assert c.post("/wallets/ama/in", json={"amount": 0}).status_code == 422
```
