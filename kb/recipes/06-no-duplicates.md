# No duplicates: a value must be unique

Use when: the client says two records may not share a value (the same phone number, code, username or plate number
registered twice). Check before saving and refuse with 409 Conflict. Also add `unique=True` on the column as a safety net.
Compare case-insensitively when "Kofi" and "kofi" should count as the same.

```python
from fastapi import FastAPI, HTTPException
from sqlmodel import Field, Session, SQLModel, create_engine, func, select
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)


SQLModel.metadata.create_all(engine)
app = FastAPI()


@app.post("/accounts", status_code=201)
def register(a: Account) -> Account:
    with Session(engine) as s:
        exists = s.exec(select(Account).where(func.lower(Account.username) == a.username.lower())).first()
        if exists:
            raise HTTPException(409, f"Username {a.username!r} is already taken")
        s.add(a)
        s.commit()
        s.refresh(a)
        return a
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
assert c.post("/accounts", json={"username": "kofi"}).status_code == 201
assert c.post("/accounts", json={"username": "Kofi"}).status_code == 409
```
