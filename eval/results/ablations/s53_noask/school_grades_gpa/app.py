import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field as PField
from sqlmodel import SQLModel, Field, Session, create_engine, select, UniqueConstraint

DB_FILE = os.environ.get("RESULTS_DB", "results.db")
engine = create_engine(f"sqlite:///{DB_FILE}", connect_args={"check_same_thread": False})


class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_number: str = Field(index=True, unique=True)
    name: str


class Course(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    title: str


class Score(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("student_id", "course_id"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id", index=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    score: float


class StudentIn(BaseModel):
    student_number: str = PField(min_length=1)
    name: str = PField(min_length=1)


class CourseIn(BaseModel):
    code: str = PField(min_length=1)
    title: str = PField(min_length=1)


class ScoreIn(BaseModel):
    student_id: int
    course_id: int
    score: float = PField(ge=0, le=100)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Student Results", lifespan=lifespan)


def get_session():
    with Session(engine) as session:
        yield session


# Grading scale: (minimum score, grade, grade point)
GRADES = [
    (80, "A", 4.0),
    (75, "B+", 3.5),
    (70, "B", 3.0),
    (65, "C+", 2.5),
    (60, "C", 2.0),
    (55, "D+", 1.5),
    (50, "D", 1.0),
    (0, "E", 0.0),
]


def grade_for(score: float):
    for minimum, letter, point in GRADES:
        if score >= minimum:
            return letter, point
    return "E", 0.0


@app.post("/students", status_code=201)
def create_student(data: StudentIn, session: Session = Depends(get_session)):
    number = data.student_number.strip()
    if session.exec(select(Student).where(Student.student_number == number)).first():
        raise HTTPException(409, "A student with this student number already exists")
    student = Student(student_number=number, name=data.name.strip())
    session.add(student)
    session.commit()
    session.refresh(student)
    return student


@app.get("/students")
def list_students(session: Session = Depends(get_session)):
    return session.exec(select(Student).order_by(Student.id)).all()


@app.get("/students/{student_id}")
def get_student(student_id: int, session: Session = Depends(get_session)):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(404, "Student not found")
    return student


@app.post("/courses", status_code=201)
def create_course(data: CourseIn, session: Session = Depends(get_session)):
    code = data.code.strip()
    if session.exec(select(Course).where(Course.code == code)).first():
        raise HTTPException(409, "A course with this code already exists")
    course = Course(code=code, title=data.title.strip())
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


@app.get("/courses")
def list_courses(session: Session = Depends(get_session)):
    return session.exec(select(Course).order_by(Course.id)).all()


@app.get("/courses/{course_id}")
def get_course(course_id: int, session: Session = Depends(get_session)):
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    return course


@app.post("/scores")
def enter_score(data: ScoreIn, session: Session = Depends(get_session)):
    if not session.get(Student, data.student_id):
        raise HTTPException(404, "Student not found")
    if not session.get(Course, data.course_id):
        raise HTTPException(404, "Course not found")
    existing = session.exec(
        select(Score).where(Score.student_id == data.student_id, Score.course_id == data.course_id)
    ).first()
    if existing:
        existing.score = data.score
        record = existing
    else:
        record = Score(student_id=data.student_id, course_id=data.course_id, score=data.score)
    session.add(record)
    session.commit()
    session.refresh(record)
    letter, point = grade_for(record.score)
    return {
        "student_id": record.student_id,
        "course_id": record.course_id,
        "score": record.score,
        "grade": letter,
        "grade_point": point,
    }


@app.get("/students/{student_id}/results")
def student_results(student_id: int, session: Session = Depends(get_session)):
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(404, "Student not found")
    rows = session.exec(
        select(Score, Course).where(Score.student_id == student_id, Score.course_id == Course.id).order_by(Course.code)
    ).all()
    results = []
    for score, course in rows:
        letter, point = grade_for(score.score)
        results.append({
            "course_id": course.id,
            "course_code": course.code,
            "course_title": course.title,
            "score": score.score,
            "grade": letter,
            "grade_point": point,
        })
    gpa = round(sum(r["grade_point"] for r in results) / len(results), 2) if results else None
    return {
        "student_id": student.id,
        "student_number": student.student_number,
        "name": student.name,
        "results": results,
        "gpa": gpa,
    }
