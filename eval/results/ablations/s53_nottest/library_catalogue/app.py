from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, func

engine = create_engine("sqlite:///library.db", connect_args={"check_same_thread": False})


class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    author: str
    copies: int


class Loan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(index=True, foreign_key="book.id")
    student_name: str = Field(index=True)


class BookIn(BaseModel):
    title: str
    author: str
    copies: int

    @field_validator("title", "author")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("copies")
    @classmethod
    def positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("must be at least 1")
        return v


class StudentIn(BaseModel):
    student_name: str

    @field_validator("student_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


app = FastAPI(title="School Library")


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


def loans_count(session: Session, book_id: int) -> int:
    return session.exec(select(func.count()).select_from(Loan).where(Loan.book_id == book_id)).one()


def book_out(session: Session, book: Book) -> dict:
    out = loans_count(session, book.id)
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "copies": book.copies,
        "available": book.copies - out,
    }


def get_book_or_404(session: Session, book_id: int) -> Book:
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.post("/books", status_code=201)
def add_book(data: BookIn):
    with Session(engine) as session:
        book = Book(title=data.title, author=data.author, copies=data.copies)
        session.add(book)
        session.commit()
        session.refresh(book)
        return book_out(session, book)


@app.get("/books")
def list_books():
    with Session(engine) as session:
        books = session.exec(select(Book).order_by(Book.id)).all()
        return [book_out(session, b) for b in books]


@app.get("/books/{book_id}")
def get_book(book_id: int):
    with Session(engine) as session:
        return book_out(session, get_book_or_404(session, book_id))


@app.post("/books/{book_id}/borrow")
def borrow_book(book_id: int, data: StudentIn):
    with Session(engine) as session:
        book = get_book_or_404(session, book_id)
        if loans_count(session, book.id) >= book.copies:
            raise HTTPException(status_code=409, detail="No copies of this book are on the shelf")
        session.add(Loan(book_id=book.id, student_name=data.student_name))
        session.commit()
        return book_out(session, book)


@app.post("/books/{book_id}/return")
def return_book(book_id: int, data: StudentIn):
    with Session(engine) as session:
        book = get_book_or_404(session, book_id)
        loan = session.exec(
            select(Loan).where(Loan.book_id == book.id, Loan.student_name == data.student_name)
        ).first()
        if not loan:
            raise HTTPException(status_code=409, detail="This student has not borrowed this book")
        session.delete(loan)
        session.commit()
        return book_out(session, book)
