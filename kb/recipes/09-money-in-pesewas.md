# Money: store whole pesewas (or cents), never floats

Use when: prices, payments, balances, fares or splitting a bill. Floats lose pennies (0.1 + 0.2 != 0.3). Store money as
an integer number of the smallest unit (pesewas: 1 cedi = 100 pesewas), convert once at the edge, and when splitting
give the leftover pesewas to the first people so the parts always add up exactly to the total.

```python
from decimal import ROUND_HALF_UP, Decimal

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()


def to_pesewas(cedis: float) -> int:
    return int((Decimal(str(cedis)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_cedis(pesewas: int) -> float:
    return pesewas / 100


def split(total: int, people: int) -> list[int]:
    """Split total pesewas into people parts that add up exactly: 1000 / 3 -> [334, 333, 333]."""
    base, extra = divmod(total, people)
    return [base + 1 if i < extra else base for i in range(people)]


class SplitIn(BaseModel):
    amount: float = Field(gt=0)  # in cedis, as the client types it
    people: int = Field(gt=0)


@app.post("/split")
def split_bill(body: SplitIn) -> list[float]:
    return [to_cedis(p) for p in split(to_pesewas(body.amount), body.people)]
```

```python check
from fastapi.testclient import TestClient
assert to_pesewas(0.1) + to_pesewas(0.2) == to_pesewas(0.3)
assert split(1000, 3) == [334, 333, 333] and sum(split(1000, 3)) == 1000
r = TestClient(app).post("/split", json={"amount": 10, "people": 3}).json()
assert r == [3.34, 3.33, 3.33]
```
