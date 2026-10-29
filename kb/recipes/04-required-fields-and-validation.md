# Required fields and simple input checks (422 for bad input)

Use when: some fields must be given, text must not be empty, numbers must be positive or within a range, a phone or code
must match a pattern. Declare the rule on the field with `Field(...)`; FastAPI then refuses bad input with 422 by itself.
- Required: no default value. Optional: give a default (`= None` or `= ""`).
- Not empty: `Field(min_length=1)`. Positive: `Field(gt=0)`. Range: `Field(ge=0, le=100)`. Pattern: `Field(pattern=r"^0\d{9}$")`.
- Blank text after trimming ("   "): add a validator, shown below.
- Write input models with pydantic's `BaseModel` and `Field`: sqlmodel's `Field` does not accept `pattern`
  ("Field() got an unexpected keyword argument 'pattern'").

```python
from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator

app = FastAPI()


class MemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=130)
    phone: str = Field(pattern=r"^0\d{9}$")  # ten digits starting with 0
    nickname: str | None = None  # optional

    @field_validator("name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


@app.post("/members", status_code=201)
def add_member(m: MemberIn) -> MemberIn:
    return m
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
assert c.post("/members", json={"name": "Esi", "age": 30, "phone": "0244000000"}).status_code == 201
assert c.post("/members", json={"age": 30, "phone": "0244000000"}).status_code == 422  # name missing
assert c.post("/members", json={"name": "  ", "age": 30, "phone": "0244000000"}).status_code == 422
assert c.post("/members", json={"name": "Esi", "age": -1, "phone": "0244000000"}).status_code == 422
assert c.post("/members", json={"name": "Esi", "age": 30, "phone": "12"}).status_code == 422
```
