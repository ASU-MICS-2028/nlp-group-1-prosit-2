from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
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
    returned: bool = False


class BookIn(BaseModel):
    title: str = Field(min_length=1, pattern=r".*\S.*")
    author: str = Field(min_length=1, pattern=r".*\S.*")
    copies: int = Field(ge=1)


class StudentIn(BaseModel):
    student: str = Field(min_length=1, pattern=r".*\S.*")


engine = create_engine("sqlite:///library.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)

app = FastAPI()


def out(s, b):
    out_count = s.exec(
        select(func.count()).select_from(Loan).where(Loan.book_id == b.id, Loan.returned == False)  # noqa: E712
    ).one()
    return {"id": b.id, "title": b.title, "author": b.author, "copies": b.copies,
            "available": b.copies - out_count}


def get_book(s, book_id):
    b = s.get(Book, book_id)
    if not b:
        raise HTTPException(404, "Book not found")
    return b


@app.post("/books", status_code=201)
def add_book(data: BookIn):
    with Session(engine) as s:
        b = Book(title=data.title.strip(), author=data.author.strip(), copies=data.copies)
        s.add(b)
        s.commit()
        s.refresh(b)
        return out(s, b)


@app.get("/books")
def list_books():
    with Session(engine) as s:
        return [out(s, b) for b in s.exec(select(Book).order_by(Book.id)).all()]


@app.get("/books/{book_id}")
def read_book(book_id: int):
    with Session(engine) as s:
        return out(s, get_book(s, book_id))


@app.post("/books/{book_id}/borrow", status_code=201)
def borrow(book_id: int, data: StudentIn):
    name = data.student.strip()
    with Session(engine) as s:
        b = get_book(s, book_id)
        if out(s, b)["available"] <= 0:
            raise HTTPException(409, "No copies available")
        existing = s.exec(select(Loan).where(Loan.book_id == book_id, Loan.student == name,
                                             Loan.returned == False)).first()  # noqa: E712
        if existing:
            raise HTTPException(409, "Student already has this book")
        s.add(Loan(book_id=book_id, student=name))
        s.commit()
        return out(s, b)


@app.post("/books/{book_id}/return")
def return_book(book_id: int, data: StudentIn):
    name = data.student.strip()
    with Session(engine) as s:
        b = get_book(s, book_id)
        loan = s.exec(select(Loan).where(Loan.book_id == book_id, Loan.student == name,
                                         Loan.returned == False)).first()  # noqa: E712
        if not loan:
            raise HTTPException(409, "Student has not borrowed this book")
        loan.returned = True
        s.add(loan)
        s.commit()
        return out(s, b)
