from threading import Lock
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, StrictInt, field_validator

app = FastAPI(title="School Library Catalogue")

_lock = Lock()
_books: Dict[int, dict] = {}
_next_id = 1


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    author: str = Field(..., min_length=1, max_length=200)
    copies: StrictInt = Field(..., ge=1, le=100000)

    @field_validator("title", "author")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class StudentAction(BaseModel):
    student_name: str = Field(..., min_length=1, max_length=200)

    @field_validator("student_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("must not be blank")
        return v


def _key(name: str) -> str:
    return name.casefold()


def _public(book: dict) -> dict:
    borrowed = sum(book["loans"].values())
    return {
        "id": book["id"],
        "title": book["title"],
        "author": book["author"],
        "copies_owned": book["copies"],
        "copies_borrowed": borrowed,
        "copies_available": book["copies"] - borrowed,
    }


def _get(book_id: int) -> dict:
    book = _books.get(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.post("/books", status_code=201)
def add_book(data: BookCreate) -> dict:
    global _next_id
    with _lock:
        book = {
            "id": _next_id,
            "title": data.title,
            "author": data.author,
            "copies": data.copies,
            "loans": {},  # student key -> number of copies held
        }
        _books[_next_id] = book
        _next_id += 1
        return _public(book)


@app.get("/books")
def list_books() -> List[dict]:
    with _lock:
        return [_public(b) for b in _books.values()]


@app.get("/books/{book_id}")
def get_book(book_id: int) -> dict:
    with _lock:
        return _public(_get(book_id))


@app.post("/books/{book_id}/borrow")
def borrow_book(book_id: int, data: StudentAction) -> dict:
    with _lock:
        book = _get(book_id)
        available = book["copies"] - sum(book["loans"].values())
        if available <= 0:
            raise HTTPException(
                status_code=409,
                detail="All copies of this book are currently borrowed",
            )
        k = _key(data.student_name)
        book["loans"][k] = book["loans"].get(k, 0) + 1
        return {
            "message": f"{data.student_name} borrowed '{book['title']}'",
            "book": _public(book),
        }


@app.post("/books/{book_id}/return")
def return_book(book_id: int, data: StudentAction) -> dict:
    with _lock:
        book = _get(book_id)
        k = _key(data.student_name)
        held = book["loans"].get(k, 0)
        if held <= 0:
            raise HTTPException(
                status_code=409,
                detail="This student has not borrowed this book",
            )
        if held == 1:
            del book["loans"][k]
        else:
            book["loans"][k] = held - 1
        return {
            "message": f"{data.student_name} returned '{book['title']}'",
            "book": _public(book),
        }
