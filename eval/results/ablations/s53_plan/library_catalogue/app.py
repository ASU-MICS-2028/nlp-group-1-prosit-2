from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictInt, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, func, select

engine = create_engine(
    "sqlite:///library.db", connect_args={"check_same_thread": False}
)


class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    author: str
    copies: int


class Loan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", index=True)
    student_name: str = Field(index=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="School Library Catalogue", lifespan=lifespan)


def _not_blank(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("must not be empty")
    return v


class BookIn(BaseModel):
    title: str
    author: str
    copies: StrictInt

    @field_validator("title", "author")
    @classmethod
    def check_text(cls, v: str) -> str:
        return _not_blank(v)

    @field_validator("copies")
    @classmethod
    def check_copies(cls, v: int) -> int:
        if v < 0:
            raise ValueError("cannot be below zero")
        return v


class StudentIn(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str) -> str:
        return _not_blank(v)


def _borrowed_count(session: Session, book_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(Loan).where(Loan.book_id == book_id)
    ).one()


def _book_out(session: Session, book: Book) -> dict:
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "copies": book.copies,
        "on_shelf": book.copies - _borrowed_count(session, book.id),
    }


def _get_book(session: Session, book_id: int) -> Book:
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.post("/books", status_code=201)
def add_book(data: BookIn):
    with Session(engine) as session:
        book = Book(title=data.title, author=data.author, copies=data.copies)
        session.add(book)
        session.commit()
        session.refresh(book)
        return _book_out(session, book)


@app.get("/books")
def list_books():
    with Session(engine) as session:
        books = session.exec(select(Book).order_by(Book.id)).all()
        return [_book_out(session, b) for b in books]


@app.get("/books/{book_id}")
def get_book(book_id: int):
    with Session(engine) as session:
        return _book_out(session, _get_book(session, book_id))


@app.post("/books/{book_id}/borrow", status_code=201)
def borrow_book(book_id: int, data: StudentIn):
    with Session(engine) as session:
        book = _get_book(session, book_id)
        if book.copies - _borrowed_count(session, book_id) <= 0:
            raise HTTPException(status_code=409, detail="No copies left on the shelf")
        loan = Loan(book_id=book_id, student_name=data.name)
        session.add(loan)
        session.commit()
        session.refresh(loan)
        return {
            "loan_id": loan.id,
            "student_name": loan.student_name,
            "book": _book_out(session, book),
        }


@app.post("/books/{book_id}/return")
def return_book(book_id: int, data: StudentIn):
    with Session(engine) as session:
        book = _get_book(session, book_id)
        loan = session.exec(
            select(Loan)
            .where(Loan.book_id == book_id, Loan.student_name == data.name)
            .order_by(Loan.id)
        ).first()
        if loan is None:
            raise HTTPException(
                status_code=409,
                detail="This student does not have a copy of this book borrowed",
            )
        session.delete(loan)
        session.commit()
        return {"student_name": data.name, "book": _book_out(session, book)}
