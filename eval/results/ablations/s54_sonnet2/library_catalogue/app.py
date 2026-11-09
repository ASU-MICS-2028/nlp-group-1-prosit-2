from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator, Field
from sqlmodel import SQLModel, Field as F, Session, create_engine, select, func


class Book(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    title: str
    author: str
    copies: int


class Loan(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    book_id: int = F(index=True)
    student: str


class BookIn(BaseModel):
    title: str
    author: str
    copies: int = Field(ge=1)

    @field_validator("title", "author")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class StudentIn(BaseModel):
    student: str

    @field_validator("student")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


engine = create_engine("sqlite:///library.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)

app = FastAPI()


def out(s, b):
    n = s.exec(select(func.count()).select_from(Loan).where(Loan.book_id == b.id)).one()
    return {"id": b.id, "title": b.title, "author": b.author,
            "copies": b.copies, "available": b.copies - n}


def get_book(s, book_id):
    b = s.get(Book, book_id)
    if not b:
        raise HTTPException(404, "Book not found")
    return b


@app.post("/books", status_code=201)
def add_book(data: BookIn):
    with Session(engine) as s:
        b = Book(title=data.title, author=data.author, copies=data.copies)
        s.add(b)
        s.commit()
        s.refresh(b)
        return out(s, b)


@app.get("/books")
def list_books():
    with Session(engine) as s:
        return [out(s, b) for b in s.exec(select(Book)).all()]


@app.get("/books/{book_id}")
def one_book(book_id: int):
    with Session(engine) as s:
        return out(s, get_book(s, book_id))


@app.post("/books/{book_id}/borrow", status_code=201)
def borrow(book_id: int, data: StudentIn):
    with Session(engine) as s:
        b = get_book(s, book_id)
        if s.exec(select(Loan).where(Loan.book_id == book_id, Loan.student == data.student)).first():
            raise HTTPException(409, "Student already has this book")
        if out(s, b)["available"] <= 0:
            raise HTTPException(409, "No copies available")
        s.add(Loan(book_id=book_id, student=data.student))
        s.commit()
        return out(s, b)


@app.post("/books/{book_id}/return")
def return_book(book_id: int, data: StudentIn):
    with Session(engine) as s:
        b = get_book(s, book_id)
        loan = s.exec(select(Loan).where(Loan.book_id == book_id, Loan.student == data.student)).first()
        if not loan:
            raise HTTPException(409, "Student has not borrowed this book")
        s.delete(loan)
        s.commit()
        return out(s, b)
