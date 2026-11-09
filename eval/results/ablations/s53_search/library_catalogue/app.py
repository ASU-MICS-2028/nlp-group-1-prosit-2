from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, text

DATABASE_URL = "sqlite:///./library.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    author: str
    copies: int
    available: int


class Loan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(index=True, foreign_key="book.id")
    student_name: str = Field(index=True)


class BookIn(BaseModel):
    title: str
    author: str
    copies: int = PField(ge=1)

    @field_validator("title", "author")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
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


class BookOut(BaseModel):
    id: int
    title: str
    author: str
    copies: int
    available: int


app = FastAPI(title="School Library Catalogue")


@app.on_event("startup")
def on_startup() -> None:
    SQLModel.metadata.create_all(engine)


def to_out(b: Book) -> BookOut:
    return BookOut(id=b.id, title=b.title, author=b.author, copies=b.copies, available=b.available)


@app.post("/books", status_code=201, response_model=BookOut)
def add_book(data: BookIn):
    with Session(engine) as s:
        b = Book(title=data.title, author=data.author, copies=data.copies, available=data.copies)
        s.add(b)
        s.commit()
        s.refresh(b)
        return to_out(b)


@app.get("/books", response_model=List[BookOut])
def list_books():
    with Session(engine) as s:
        return [to_out(b) for b in s.exec(select(Book).order_by(Book.id)).all()]


@app.get("/books/{book_id}", response_model=BookOut)
def get_book(book_id: int):
    with Session(engine) as s:
        b = s.get(Book, book_id)
        if not b:
            raise HTTPException(404, "Book not found")
        return to_out(b)


@app.post("/books/{book_id}/borrow", response_model=BookOut)
def borrow(book_id: int, data: StudentIn):
    with Session(engine) as s:
        if not s.get(Book, book_id):
            raise HTTPException(404, "Book not found")
        # Atomic: only take a copy if one is still on the shelf.
        res = s.execute(
            text("UPDATE book SET available = available - 1 WHERE id = :id AND available > 0"),
            {"id": book_id},
        )
        if res.rowcount != 1:
            s.rollback()
            raise HTTPException(409, "All copies of this book are currently borrowed")
        s.add(Loan(book_id=book_id, student_name=data.student_name))
        s.commit()
        b = s.get(Book, book_id)
        s.refresh(b)
        return to_out(b)


@app.post("/books/{book_id}/return", response_model=BookOut)
def return_book(book_id: int, data: StudentIn):
    with Session(engine) as s:
        if not s.get(Book, book_id):
            raise HTTPException(404, "Book not found")
        # Atomic: remove exactly one loan held by this student for this book.
        res = s.execute(
            text(
                "DELETE FROM loan WHERE id = (SELECT id FROM loan WHERE book_id = :b "
                "AND student_name = :n LIMIT 1)"
            ),
            {"b": book_id, "n": data.student_name},
        )
        if res.rowcount != 1:
            s.rollback()
            raise HTTPException(409, "This student has not borrowed this book")
        s.execute(text("UPDATE book SET available = available + 1 WHERE id = :id"), {"id": book_id})
        s.commit()
        b = s.get(Book, book_id)
        s.refresh(b)
        return to_out(b)
