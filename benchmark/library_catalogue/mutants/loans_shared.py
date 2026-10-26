# MUTANT loans_shared: '    if not any(l.borrower in ls for ls in loans.values()):\n        raise HTTPException(400, "This student has not borrowed this book")\n    if l.borrower in loans[book_id]:\n        loans[book_id].remove(l.borrower)\n' instead of '    if l.borrower not in loans[book_id]:\n        raise HTTPException(400, "This student has not borrowed this book")\n    loans[book_id].remove(l.borrower)\n'
# Reference backend for library_catalogue: proves the hidden tests are right.
# Deliberately uses different names (book_title, writer, total_copies, on_shelf, borrower) to exercise ops.json translation.
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
books, loans = {}, {}


class BookIn(BaseModel):
    book_title: str
    writer: str
    total_copies: int


class LoanIn(BaseModel):
    borrower: str


def find(book_id):
    if book_id not in books:
        raise HTTPException(404, "No such book")
    return books[book_id]


@app.post("/catalogue/books", status_code=201)
def add_book(b: BookIn):
    book = {"id": len(books) + 1, **b.model_dump(), "on_shelf": b.total_copies}
    books[book["id"]] = book
    loans[book["id"]] = []
    return book


@app.get("/catalogue/books")
def list_books():
    return list(books.values())


@app.get("/catalogue/books/{book_id}")
def get_book(book_id: int):
    return find(book_id)


@app.post("/catalogue/books/{book_id}/loans", status_code=201)
def borrow_book(book_id: int, l: LoanIn):
    book = find(book_id)
    if book["on_shelf"] <= 0:
        raise HTTPException(409, "No copies left on the shelf")
    book["on_shelf"] -= 1
    loans[book_id].append(l.borrower)
    return book


@app.post("/catalogue/books/{book_id}/returns")
def return_book(book_id: int, l: LoanIn):
    book = find(book_id)
    if not any(l.borrower in ls for ls in loans.values()):
        raise HTTPException(400, "This student has not borrowed this book")
    if l.borrower in loans[book_id]:
        loans[book_id].remove(l.borrower)
    book["on_shelf"] += 1
    return book
