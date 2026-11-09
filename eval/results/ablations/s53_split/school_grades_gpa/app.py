from contextlib import asynccontextmanager
from typing import Annotated, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field as SQLField, Session, SQLModel, UniqueConstraint, create_engine, select

DATABASE_URL = "sqlite:///./results.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


# ---------- Database tables ----------
class Student(SQLModel, table=True):
    student_number: str = SQLField(primary_key=True)
    full_name: str


class Course(SQLModel, table=True):
    code: str = SQLField(primary_key=True)
    title: str
    credit_hours: int


class Score(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("student_number", "course_code"),)
    id: Optional[int] = SQLField(default=None, primary_key=True)
    student_number: str = SQLField(foreign_key="student.student_number", index=True)
    course_code: str = SQLField(foreign_key="course.code")
    score: float


# ---------- Request bodies ----------
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]


class StudentIn(BaseModel):
    student_number: Text
    full_name: Text


class CourseIn(BaseModel):
    code: Text
    title: Text
    credit_hours: int = Field(strict=True, ge=1, le=6)


class ScoreIn(BaseModel):
    score: float = Field(strict=True, ge=0, le=100, allow_inf_nan=False)


# ---------- Grading ----------
GRADE_SCALE = [
    (80, "A", 4.0),
    (75, "B+", 3.5),
    (70, "B", 3.0),
    (65, "C+", 2.5),
    (60, "C", 2.0),
    (55, "D+", 1.5),
    (50, "D", 1.0),
    (0, "F", 0.0),
]


def grade_for(score: float):
    for minimum, letter, points in GRADE_SCALE:
        if score >= minimum:
            return letter, points
    return "F", 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="College Results", lifespan=lifespan)


@app.post("/students", status_code=201)
def register_student(body: StudentIn):
    with Session(engine) as session:
        if session.get(Student, body.student_number):
            raise HTTPException(409, "This student number is already in use.")
        student = Student(student_number=body.student_number, full_name=body.full_name)
        session.add(student)
        try:
            session.commit()
        except IntegrityError:
            raise HTTPException(409, "This student number is already in use.")
        return {"student_number": student.student_number, "full_name": student.full_name}


@app.post("/courses", status_code=201)
def register_course(body: CourseIn):
    with Session(engine) as session:
        if session.get(Course, body.code):
            raise HTTPException(409, "This course code is already in use.")
        course = Course(code=body.code, title=body.title, credit_hours=body.credit_hours)
        session.add(course)
        try:
            session.commit()
        except IntegrityError:
            raise HTTPException(409, "This course code is already in use.")
        return {"code": course.code, "title": course.title, "credit_hours": course.credit_hours}


@app.put("/students/{student_number}/scores/{course_code}")
def enter_score(student_number: str, course_code: str, body: ScoreIn):
    with Session(engine) as session:
        if not session.get(Student, student_number):
            raise HTTPException(404, "Student not found.")
        course = session.get(Course, course_code)
        if not course:
            raise HTTPException(404, "Course not found.")
        existing = session.exec(
            select(Score).where(Score.student_number == student_number, Score.course_code == course_code)
        ).first()
        if existing:
            existing.score = body.score
            session.add(existing)
        else:
            session.add(Score(student_number=student_number, course_code=course_code, score=body.score))
        session.commit()
        letter, points = grade_for(body.score)
        return {
            "student_number": student_number,
            "course_code": course_code,
            "score": body.score,
            "grade": letter,
            "grade_points": points,
        }


@app.get("/students/{student_number}/results")
def student_results(student_number: str):
    with Session(engine) as session:
        student = session.get(Student, student_number)
        if not student:
            raise HTTPException(404, "Student not found.")
        rows = session.exec(
            select(Score, Course)
            .where(Score.student_number == student_number, Score.course_code == Course.code)
            .order_by(Course.code)
        ).all()
        results = []
        total_points = 0.0
        total_hours = 0
        for score, course in rows:
            letter, points = grade_for(score.score)
            results.append({
                "course_code": course.code,
                "course_title": course.title,
                "credit_hours": course.credit_hours,
                "score": score.score,
                "grade": letter,
                "grade_points": points,
            })
            total_points += points * course.credit_hours
            total_hours += course.credit_hours
        gpa = round(total_points / total_hours, 2) if total_hours else None
        return {
            "student_number": student.student_number,
            "full_name": student.full_name,
            "results": results,
            "total_credit_hours": total_hours,
            "gpa": gpa,
        }
