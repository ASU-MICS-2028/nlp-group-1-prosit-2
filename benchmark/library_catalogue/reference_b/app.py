# Second correct backend for library_catalogue: text ids, 200 on create, 422 for refusals, other paths and names.
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
books = {}


class BookIn(BaseModel):
    name: str
    by: str
    count: int


class StudentIn(BaseModel):
    student_name: str


def find(book_id):
    if book_id not in books:
        raise HTTPException(404, "No such book")
    return books[book_id]


@app.post("/books")
def add_book(b: BookIn):
    book = {"book_id": uuid.uuid4().hex, **b.model_dump(), "left": b.count, "out_to": []}
    books[book["book_id"]] = book
    return book


@app.get("/books")
def list_books():
    return list(books.values())


@app.get("/books/{book_id}")
def get_book(book_id: str):
    return find(book_id)


@app.post("/books/{book_id}/borrow")
def borrow_book(book_id: str, s: StudentIn):
    book = find(book_id)
    if book["left"] == 0:
        raise HTTPException(422, "All copies are out")
    book["left"] -= 1
    book["out_to"].append(s.student_name)
    return book


@app.post("/books/{book_id}/return")
def return_book(book_id: str, s: StudentIn):
    book = find(book_id)
    if s.student_name not in book["out_to"]:
        raise HTTPException(422, "Not borrowed by this student")
    book["out_to"].remove(s.student_name)
    book["left"] += 1
    return book
