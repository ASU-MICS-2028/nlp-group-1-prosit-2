from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import UniqueConstraint
from sqlmodel import Field as SQLField, Session, SQLModel, create_engine, select


# ---------- database tables ----------

class Student(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str


class Course(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    code: str = SQLField(index=True, unique=True)
    title: str
    credit_hours: int


class ScoreRecord(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("student_id", "course_id"),)
    id: Optional[int] = SQLField(default=None, primary_key=True)
    student_id: int = SQLField(foreign_key="student.id")
    course_id: int = SQLField(foreign_key="course.id")
    score: int


engine = create_engine(
    "sqlite:///./results.db", connect_args={"check_same_thread": False}
)


SQLModel.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="College Results", lifespan=lifespan)


# ---------- request bodies ----------

class StudentIn(BaseModel):
    name: str = Field(min_length=1)


class CourseIn(BaseModel):
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    credit_hours: int = Field(ge=1, le=6)


class ScoreIn(BaseModel):
    student_id: int
    course_id: int
    score: int = Field(ge=0, le=100)


# ---------- grading ----------

GRADE_TABLE = [
    (80, "A", 4.0),
    (75, "B+", 3.5),
    (70, "B", 3.0),
    (65, "C+", 2.5),
    (60, "C", 2.0),
    (55, "D+", 1.5),
    (50, "D", 1.0),
]


def grade_for(score: int):
    for minimum, letter, points in GRADE_TABLE:
        if score >= minimum:
            return letter, points
    return "F", 0.0


# ---------- endpoints ----------

@app.post("/students", status_code=201)
def register_student(body: StudentIn):
    with Session(engine) as session:
        student = Student(name=body.name)
        session.add(student)
        session.commit()
        session.refresh(student)
        return {"id": student.id, "name": student.name}


@app.post("/courses", status_code=201)
def register_course(body: CourseIn):
    with Session(engine) as session:
        exists = session.exec(select(Course).where(Course.code == body.code)).first()
        if exists:
            raise HTTPException(status_code=409, detail="A course with this code already exists")
        course = Course(code=body.code, title=body.title, credit_hours=body.credit_hours)
        session.add(course)
        session.commit()
        session.refresh(course)
        return {
            "id": course.id,
            "code": course.code,
            "title": course.title,
            "credit_hours": course.credit_hours,
        }


@app.post("/scores", status_code=201)
def enter_score(body: ScoreIn):
    with Session(engine) as session:
        if session.get(Student, body.student_id) is None:
            raise HTTPException(status_code=404, detail="Student not found")
        if session.get(Course, body.course_id) is None:
            raise HTTPException(status_code=404, detail="Course not found")
        record = session.exec(
            select(ScoreRecord).where(
                ScoreRecord.student_id == body.student_id,
                ScoreRecord.course_id == body.course_id,
            )
        ).first()
        if record is None:
            record = ScoreRecord(
                student_id=body.student_id,
                course_id=body.course_id,
                score=body.score,
            )
        else:
            # a re-entered score replaces the earlier one
            record.score = body.score
        session.add(record)
        session.commit()
        session.refresh(record)
        letter, points = grade_for(record.score)
        return {
            "student_id": record.student_id,
            "course_id": record.course_id,
            "score": record.score,
            "grade": letter,
            "grade_points": points,
        }


@app.get("/students/{student_id}/results")
def student_results(student_id: int):
    with Session(engine) as session:
        student = session.get(Student, student_id)
        if student is None:
            raise HTTPException(status_code=404, detail="Student not found")
        rows = session.exec(
            select(ScoreRecord, Course)
            .where(ScoreRecord.student_id == student_id)
            .where(Course.id == ScoreRecord.course_id)
            .order_by(Course.code)
        ).all()
        courses = []
        total_points = 0.0
        total_hours = 0
        for record, course in rows:
            letter, points = grade_for(record.score)
            total_points += points * course.credit_hours
            total_hours += course.credit_hours
            courses.append({
                "course_id": course.id,
                "code": course.code,
                "title": course.title,
                "credit_hours": course.credit_hours,
                "score": record.score,
                "grade": letter,
                "grade_points": points,
            })
        gpa = round(total_points / total_hours, 2) if total_hours else None
        return {
            "student_id": student.id,
            "name": student.name,
            "courses": courses,
            "gpa": gpa,
        }
