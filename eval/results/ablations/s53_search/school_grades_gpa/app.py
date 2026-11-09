from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, StrictFloat, StrictInt, field_validator
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select, Field as SQLField

engine = create_engine(
    "sqlite:///./results.db", connect_args={"check_same_thread": False}
)


class Student(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str


class Course(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str
    credit_hours: int


class Score(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("student_id", "course_id"),)
    id: Optional[int] = SQLField(default=None, primary_key=True)
    student_id: int = SQLField(foreign_key="student.id", index=True)
    course_id: int = SQLField(foreign_key="course.id")
    score: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Student Results", lifespan=lifespan)


class StudentIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


class CourseIn(StudentIn):
    credit_hours: StrictInt = Field(ge=1, le=6)


class ScoreIn(BaseModel):
    student_id: StrictInt
    course_id: StrictInt
    score: StrictInt | StrictFloat = Field(ge=0, le=100)


GRADES = [
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
    for low, letter, points in GRADES:
        if score >= low:
            return letter, points
    return "F", 0.0


@app.post("/students", status_code=201)
def create_student(data: StudentIn):
    with Session(engine) as s:
        st = Student(name=data.name)
        s.add(st)
        s.commit()
        s.refresh(st)
        return st


@app.get("/students")
def list_students():
    with Session(engine) as s:
        return s.exec(select(Student).order_by(Student.id)).all()


@app.post("/courses", status_code=201)
def create_course(data: CourseIn):
    with Session(engine) as s:
        c = Course(name=data.name, credit_hours=data.credit_hours)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


@app.get("/courses")
def list_courses():
    with Session(engine) as s:
        return s.exec(select(Course).order_by(Course.id)).all()


@app.post("/scores")
def enter_score(data: ScoreIn):
    """Enter a score; entering again for the same student and course replaces it."""
    with Session(engine) as s:
        if not s.get(Student, data.student_id):
            raise HTTPException(404, "Student not found")
        if not s.get(Course, data.course_id):
            raise HTTPException(404, "Course not found")
        for _ in range(2):
            existing = s.exec(
                select(Score).where(
                    Score.student_id == data.student_id,
                    Score.course_id == data.course_id,
                )
            ).first()
            if existing:
                existing.score = float(data.score)
                row = existing
            else:
                row = Score(
                    student_id=data.student_id,
                    course_id=data.course_id,
                    score=float(data.score),
                )
            s.add(row)
            try:
                s.commit()
                break
            except IntegrityError:
                s.rollback()
        else:
            raise HTTPException(409, "Could not save score, please try again")
        s.refresh(row)
        letter, points = grade_for(row.score)
        return {
            "student_id": row.student_id,
            "course_id": row.course_id,
            "score": row.score,
            "grade": letter,
            "grade_point": points,
        }


@app.get("/students/{student_id}/results")
def student_results(student_id: int):
    with Session(engine) as s:
        st = s.get(Student, student_id)
        if not st:
            raise HTTPException(404, "Student not found")
        rows = s.exec(
            select(Score, Course)
            .join(Course, Course.id == Score.course_id)
            .where(Score.student_id == student_id)
            .order_by(Course.id)
        ).all()
        results: List[dict] = []
        total_points = 0.0
        total_hours = 0
        for sc, c in rows:
            letter, points = grade_for(sc.score)
            results.append(
                {
                    "course_id": c.id,
                    "course_name": c.name,
                    "credit_hours": c.credit_hours,
                    "score": sc.score,
                    "grade": letter,
                    "grade_point": points,
                }
            )
            total_points += points * c.credit_hours
            total_hours += c.credit_hours
        gpa = round(total_points / total_hours, 2) if total_hours else None
        return {
            "student_id": st.id,
            "name": st.name,
            "results": results,
            "total_credit_hours": total_hours,
            "gpa": gpa,
        }
