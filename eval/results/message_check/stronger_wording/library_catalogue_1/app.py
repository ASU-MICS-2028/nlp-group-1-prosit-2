import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Field as SQLField, Session, SQLModel, create_engine, func, select

DATABASE_URL = "sqlite:///./library.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
loan_lock = threading.Lock()


class Book(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    title: str
    author: str
    copies_owned: int


class Loan(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    book_id: int = SQLField(foreign_key="book.id", index=True)
    student_name: str = SQLField(index=True)
    borrowed_at: datetime
    returned_at: Optional[datetime] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="School Library Catalogue", lifespan=lifespan)


def _clean_text(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label} cannot be empty")
    return value


class StudentName(BaseModel):
    name: str = Field(max_length=200)

    @field_validator("name")
    @classmethod
    def check_name(cls, v):
        return _clean_text(v, "Name")


def _copies_out(session: Session, book_id: int) -> int:
    return session.exec(
        select(func.count(Loan.id)).where(Loan.book_id == book_id, Loan.returned_at.is_(None))
    ).one()


def _book_out(session: Session, book: Book) -> dict:
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "copies_owned": book.copies_owned,
        "copies_on_shelf": book.copies_owned - _copies_out(session, book.id),
    }


def _get_book(session: Session, book_id: int) -> Book:
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


def _loan_out(loan: Loan) -> dict:
    return {
        "id": loan.id,
        "book_id": loan.book_id,
        "student_name": loan.student_name,
        "borrowed_at": loan.borrowed_at.isoformat(),
        "returned_at": loan.returned_at.isoformat() if loan.returned_at else None,
    }


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
def borrow_book(book_id: int, data: StudentName):
    with loan_lock, Session(engine) as session:
        book = _get_book(session, book_id)
        if _copies_out(session, book.id) >= book.copies_owned:
            raise HTTPException(status_code=409, detail="No copies of this book are on the shelf")
        loan = Loan(book_id=book.id, student_name=data.name, borrowed_at=datetime.now(timezone.utc))
        session.add(loan)
        session.commit()
        session.refresh(loan)
        return {"loan": _loan_out(loan), "book": _book_out(session, book)}


@app.post("/books/{book_id}/return")
def return_book(book_id: int, data: StudentName):
    with loan_lock, Session(engine) as session:
        book = _get_book(session, book_id)
        loan = session.exec(
            select(Loan)
            .where(Loan.book_id == book.id, Loan.student_name == data.name, Loan.returned_at.is_(None))
            .order_by(Loan.borrowed_at)
        ).first()
        if loan is None:
            raise HTTPException(
                status_code=409, detail="This student does not have a copy of this book borrowed"
            )
        loan.returned_at = datetime.now(timezone.utc)
        session.add(loan)
        session.commit()
        session.refresh(loan)
        return {"loan": _loan_out(loan), "book": _book_out(session, book)}
