# Get one record by id, or 404 if it does not exist

Use when: an endpoint looks up a single record (GET /things/{id}), or any action on a record that may not exist.
`session.get(Model, id)` returns None when there is no such row; answer 404 with HTTPException, never 200 with null and never 500.

```python
from fastapi import FastAPI, HTTPException
from sqlmodel import Field, Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Book(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str


SQLModel.metadata.create_all(engine)
app = FastAPI()


def get_or_404(s: Session, book_id: int) -> Book:
    book = s.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail=f"No book with id {book_id}")
    return book


@app.post("/books", status_code=201)
def add(book: Book) -> Book:
    with Session(engine) as s:
        s.add(book)
        s.commit()
        s.refresh(book)
        return book


@app.get("/books/{book_id}")
def get_book(book_id: int) -> Book:
    with Session(engine) as s:
        return get_or_404(s, book_id)
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
b = c.post("/books", json={"title": "Things Fall Apart"}).json()
assert c.get(f"/books/{b['id']}").json()["title"] == "Things Fall Apart"
assert c.get("/books/999").status_code == 404
```
