import threading
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictStr, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, func

engine = create_engine("sqlite:///library.db", connect_args={"check_same_thread": False})
lock = threading.Lock()


class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    author: str
    copies_owned: int


class Loan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", index=True)
    student_name: str
    borrowed_at: datetime
    returned_at: Optional[datetime] = None


class StudentIn(BaseModel):
    name: StrictStr

    @field_validator("name")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name is required")
        return v


app = FastAPI(title="School Library Catalogue")


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


def out_count(session: Session, book_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(Loan).where(Loan.book_id == book_id, Loan.returned_at == None)  # noqa: E711
    ).one()


def book_view(session: Session, book: Book) -> dict:
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "copies_owned": book.copies_owned,
        "copies_on_shelf": book.copies_owned - out_count(session, book.id),
    }


def get_book_or_404(session: Session, book_id: int) -> Book:
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.get("/books")
def list_books():
    with Session(engine) as session:
        books = session.exec(select(Book).order_by(Book.id)).all()
        return [book_view(session, b) for b in books]


@app.get("/books/{bookId}")
def get_book(bookId: int):
    with Session(engine) as session:
        return book_view(session, get_book_or_404(session, bookId))


@app.post("/books/{bookId}/borrow")
def borrow_book(bookId: int, data: StudentIn):
    with lock, Session(engine) as session:
        book = get_book_or_404(session, bookId)
        if book.copies_owned - out_count(session, book.id) <= 0:
            raise HTTPException(status_code=409, detail="No copies are on the shelf")
        session.add(Loan(book_id=book.id, student_name=data.name,
                         borrowed_at=datetime.now(timezone.utc)))
        session.commit()
        return {"message": f"{data.name} borrowed '{book.title}'", "book": book_view(session, book)}


@app.post("/books/{bookId}/return")
def return_book(bookId: int, data: StudentIn):
    with lock, Session(engine) as session:
        book = get_book_or_404(session, bookId)
        loan = session.exec(
            select(Loan).where(Loan.book_id == book.id, Loan.student_name == data.name,
                               Loan.returned_at == None).order_by(Loan.id)  # noqa: E711
        ).first()
        if not loan:
            raise HTTPException(status_code=409,
                                detail="This student does not currently have a copy of this book borrowed")
        loan.returned_at = datetime.now(timezone.utc)
        session.add(loan)
        session.commit()
        return {"message": f"{data.name} returned '{book.title}'", "book": book_view(session, book)}
