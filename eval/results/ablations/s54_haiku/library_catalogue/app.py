import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, create_engine, select

engine = create_engine(
    "sqlite:///library.db",
    connect_args={"check_same_thread": False},
)

# Serialises borrow/return so two students cannot both take the last copy.
lock = threading.Lock()


class Book(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    title: str
    author: str
    copies_total: int


class Loan(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    book_id: int = SQLField(foreign_key="book.id", index=True)
    student: str
    active: bool = True


class BookIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    copies: int = Field(ge=1)


class StudentIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    student: str = Field(min_length=1)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="School Library Catalogue", lifespan=lifespan)


def book_view(session: Session, book: Book) -> dict:
    active = session.exec(
        select(Loan).where(Loan.book_id == book.id, Loan.active == True)  # noqa: E712
    ).all()
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "copies_total": book.copies_total,
        "copies_available": book.copies_total - len(active),
    }


def get_book_or_404(session: Session, book_id: int) -> Book:
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.post("/books", status_code=201)
def add_book(body: BookIn):
    with Session(engine) as session:
        book = Book(title=body.title, author=body.author, copies_total=body.copies)
        session.add(book)
        session.commit()
        session.refresh(book)
        return book_view(session, book)


@app.get("/books")
def list_books():
    with Session(engine) as session:
        books = session.exec(select(Book).order_by(Book.id)).all()
        return [book_view(session, b) for b in books]


@app.get("/books/{book_id}")
def get_book(book_id: int):
    with Session(engine) as session:
        book = get_book_or_404(session, book_id)
        return book_view(session, book)


@app.post("/books/{book_id}/borrow", status_code=201)
def borrow_book(book_id: int, body: StudentIn):
    with lock, Session(engine) as session:
        book = get_book_or_404(session, book_id)
        already = session.exec(
            select(Loan).where(
                Loan.book_id == book_id,
                Loan.student == body.student,
                Loan.active == True,  # noqa: E712
            )
        ).first()
        if already is not None:
            raise HTTPException(
                status_code=409,
                detail="This student already has a copy of this book",
            )
        view = book_view(session, book)
        if view["copies_available"] <= 0:
            raise HTTPException(status_code=409, detail="No copies left on the shelf")
        loan = Loan(book_id=book_id, student=body.student, active=True)
        session.add(loan)
        session.commit()
        session.refresh(loan)
        view = book_view(session, book)
        return {
            "loan_id": loan.id,
            "book_id": book_id,
            "student": loan.student,
            "copies_available": view["copies_available"],
        }


@app.post("/books/{book_id}/return")
def return_book(book_id: int, body: StudentIn):
    with lock, Session(engine) as session:
        book = get_book_or_404(session, book_id)
        loan = session.exec(
            select(Loan).where(
                Loan.book_id == book_id,
                Loan.student == body.student,
                Loan.active == True,  # noqa: E712
            )
        ).first()
        if loan is None:
            raise HTTPException(
                status_code=409,
                detail="This student has not borrowed this book",
            )
        loan.active = False
        session.add(loan)
        session.commit()
        return book_view(session, book)
