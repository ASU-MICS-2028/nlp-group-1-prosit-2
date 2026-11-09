from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Field as F, Session, SQLModel, create_engine, select, func


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
    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    copies: int = Field(ge=1)

    @field_validator("title", "author")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class StudentIn(BaseModel):
    student: str

    @field_validator("student")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


engine = create_engine("sqlite:///library.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)

app = FastAPI()


def out(session, book):
    borrowed = session.exec(
        select(func.count()).select_from(Loan).where(Loan.book_id == book.id)
    ).one()
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "copies": book.copies,
        "available": book.copies - borrowed,
    }


def get_book(session, book_id):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    return book


@app.post("/books", status_code=201)
def add_book(data: BookIn):
    with Session(engine) as s:
        book = Book(**data.model_dump())
        s.add(book)
        s.commit()
        s.refresh(book)
        return out(s, book)


@app.get("/books")
def list_books():
    with Session(engine) as s:
        return [out(s, b) for b in s.exec(select(Book)).all()]


@app.get("/books/{book_id}")
def read_book(book_id: int):
    with Session(engine) as s:
        return out(s, get_book(s, book_id))


@app.post("/books/{book_id}/borrow", status_code=201)
def borrow(book_id: int, data: StudentIn):
    with Session(engine) as s:
        book = get_book(s, book_id)
        if out(s, book)["available"] <= 0:
            raise HTTPException(409, "No copies available")
        s.add(Loan(book_id=book_id, student=data.student))
        s.commit()
        return out(s, book)


@app.post("/books/{book_id}/return")
def return_book(book_id: int, data: StudentIn):
    with Session(engine) as s:
        book = get_book(s, book_id)
        loan = s.exec(
            select(Loan).where(Loan.book_id == book_id, Loan.student == data.student)
        ).first()
        if not loan:
            raise HTTPException(409, "This student has not borrowed this book")
        s.delete(loan)
        s.commit()
        return out(s, book)
