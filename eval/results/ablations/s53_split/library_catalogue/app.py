import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictInt, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, func

engine = create_engine(
    "sqlite:///library.db", connect_args={"check_same_thread": False}
)
_lock = threading.Lock()


class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    author: str
    total_copies: int


class Loan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", index=True)
    student_name: str
    returned: bool = False


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
    total_copies: StrictInt

    @field_validator("title", "author")
    @classmethod
    def not_blank(cls, v: str) -> str:
        return _not_blank(v)

    @field_validator("total_copies")
    @classmethod
    def at_least_one(cls, v: int) -> int:
        if v < 1:
            raise ValueError("must be a whole number of at least 1")
        return v


class StudentIn(BaseModel):
    student_name: str

    @field_validator("student_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        return _not_blank(v)


def _borrowed_count(session: Session, book_id: int) -> int:
    return session.exec(
        select(func.count(Loan.id)).where(
            Loan.book_id == book_id, Loan.returned == False  # noqa: E712
        )
    ).one()


def _book_out(session: Session, book: Book) -> dict:
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "total_copies": book.total_copies,
        "copies_on_shelf": book.total_copies - _borrowed_count(session, book.id),
    }


def _get_book(session: Session, book_id: int) -> Book:
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.post("/books", status_code=201)
def add_book(data: BookIn):
    with Session(engine) as session:
        book = Book(title=data.title, author=data.author, total_copies=data.total_copies)
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
    with _lock, Session(engine) as session:
        book = _get_book(session, book_id)
        if book.total_copies - _borrowed_count(session, book_id) <= 0:
            raise HTTPException(
                status_code=409, detail="All copies of this book are currently borrowed"
            )
        loan = Loan(book_id=book_id, student_name=data.student_name)
        session.add(loan)
        session.commit()
        session.refresh(loan)
        return {
            "loan_id": loan.id,
            "book_id": book_id,
            "student_name": loan.student_name,
            "returned": loan.returned,
            "copies_on_shelf": book.total_copies - _borrowed_count(session, book_id),
        }


@app.post("/books/{book_id}/return")
def return_book(book_id: int, data: StudentIn):
    with _lock, Session(engine) as session:
        book = _get_book(session, book_id)
        loan = session.exec(
            select(Loan)
            .where(
                Loan.book_id == book_id,
                Loan.student_name == data.student_name,
                Loan.returned == False,  # noqa: E712
            )
            .order_by(Loan.id)
        ).first()
        if loan is None:
            raise HTTPException(
                status_code=409,
                detail="This student does not currently have a copy of this book borrowed",
            )
        loan.returned = True
        session.add(loan)
        session.commit()
        session.refresh(loan)
        return {
            "loan_id": loan.id,
            "book_id": book_id,
            "student_name": loan.student_name,
            "returned": loan.returned,
            "copies_on_shelf": book.total_copies - _borrowed_count(session, book_id),
        }
