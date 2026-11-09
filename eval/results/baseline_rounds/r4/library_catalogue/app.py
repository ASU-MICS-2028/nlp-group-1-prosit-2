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


def _key(name: str) -> str:
    return " ".join(name.split()).casefold()


def _view(book: dict) -> dict:
    borrowed = sum(len(v) for v in book["loans"].values())
    return {
        "id": book["id"],
        "title": book["title"],
        "author": book["author"],
        "total_copies": book["copies"],
        "copies_borrowed": borrowed,
        "copies_on_shelf": book["copies"] - borrowed,
    }


def _get(book_id: int) -> dict:
    book = _books.get(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.post("/books", status_code=201)
def add_book(data: BookIn):
    global _next_id
    with _lock:
        book = {
            "id": _next_id,
            "title": data.title,
            "author": data.author,
            "copies": data.copies,
            "loans": {},  # key -> list of display names (one entry per copy)
        }
        _books[_next_id] = book
        _next_id += 1
        return _view(book)


@app.get("/books")
def list_books() -> List[dict]:
    with _lock:
        return [_view(b) for b in _books.values()]


@app.get("/books/{book_id}")
def get_book(book_id: int):
    with _lock:
        return _view(_get(book_id))


@app.post("/books/{book_id}/borrow")
def borrow_book(book_id: int, data: StudentIn):
    with _lock:
        book = _get(book_id)
        if _view(book)["copies_on_shelf"] <= 0:
            raise HTTPException(
                status_code=409,
                detail="All copies of this book are currently borrowed",
            )
        book["loans"].setdefault(_key(data.student_name), []).append(data.student_name)
        result = _view(book)
        result["message"] = f"{data.student_name} borrowed '{book['title']}'"
        return result


@app.post("/books/{book_id}/return")
def return_book(book_id: int, data: StudentIn):
    with _lock:
        book = _get(book_id)
        k = _key(data.student_name)
        loans = book["loans"].get(k)
        if not loans:
            raise HTTPException(
                status_code=409,
                detail="This student has not borrowed this book",
            )
        loans.pop()
        if not loans:
            del book["loans"][k]
        result = _view(book)
        result["message"] = f"{data.student_name} returned '{book['title']}'"
        return result
