from threading import Lock
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="School Library Catalogue")

_lock = Lock()
_books: Dict[int, dict] = {}
_next_id = 1


class BookIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    author: str = Field(..., min_length=1, max_length=200)
    copies: int = Field(..., ge=1, le=100000)

    @field_validator("title", "author")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class StudentIn(BaseModel):
    student_name: str = Field(..., min_length=1, max_length=200)

    @field_validator("student_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("must not be blank")
        return v


class BookOut(BaseModel):
    id: int
    title: str
    author: str
    copies: int
    available: int
    borrowed: int


def _key(name: str) -> str:
    return name.casefold()


def _out(b: dict) -> BookOut:
    borrowed = sum(c for _, c in b["loans"].values())
    return BookOut(
        id=b["id"],
        title=b["title"],
        author=b["author"],
        copies=b["copies"],
        available=b["copies"] - borrowed,
        borrowed=borrowed,
    )


def _get(book_id: int) -> dict:
    b = _books.get(book_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return b


@app.post("/books", response_model=BookOut, status_code=201)
def add_book(data: BookIn):
    global _next_id
    with _lock:
        b = {
            "id": _next_id,
            "title": data.title,
            "author": data.author,
            "copies": data.copies,
            "loans": {},  # key -> [display_name, count]
        }
        _books[_next_id] = b
        _next_id += 1
        return _out(b)


@app.get("/books", response_model=List[BookOut])
def list_books():
    with _lock:
        return [_out(b) for b in _books.values()]


@app.get("/books/{book_id}", response_model=BookOut)
def get_book(book_id: int):
    with _lock:
        return _out(_get(book_id))


@app.post("/books/{book_id}/borrow")
def borrow_book(book_id: int, data: StudentIn):
    with _lock:
        b = _get(book_id)
        if _out(b).available <= 0:
            raise HTTPException(status_code=409, detail="All copies of this book are currently borrowed")
        k = _key(data.student_name)
        entry = b["loans"].get(k)
        if entry is None:
            b["loans"][k] = [data.student_name, 1]
        else:
            entry[1] += 1
        return {"message": f"{data.student_name} borrowed '{b['title']}'", "book": _out(b).model_dump()}


@app.post("/books/{book_id}/return")
def return_book(book_id: int, data: StudentIn):
    with _lock:
        b = _get(book_id)
        k = _key(data.student_name)
        entry = b["loans"].get(k)
        if entry is None or entry[1] <= 0:
            raise HTTPException(status_code=400, detail="This student has not borrowed this book")
        entry[1] -= 1
        if entry[1] == 0:
            del b["loans"][k]
        return {"message": f"{data.student_name} returned '{b['title']}'", "book": _out(b).model_dump()}
