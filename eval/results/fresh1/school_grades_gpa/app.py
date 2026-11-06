from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField
from sqlmodel import Field, Session, SQLModel, UniqueConstraint, create_engine, select

engine = create_engine("sqlite:///results.db", connect_args={"check_same_thread": False})


class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class Course(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    credit_hours: int


class Score(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("student_id", "course_id"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    course_id: int = Field(foreign_key="course.id")
    score: float


class StudentIn(BaseModel):
    name: str = PField(min_length=1)


class CourseIn(BaseModel):
    name: str = PField(min_length=1)
    credit_hours: int = PField(ge=1, le=6)


class ScoreIn(BaseModel):
    student_id: int
    course_id: int
    score: float = PField(ge=0, le=100)


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Student Results", lifespan=lifespan)

SCALE = [
    (80, "A", 4.0), (75, "B+", 3.5), (70, "B", 3.0), (65, "C+", 2.5),
    (60, "C", 2.0), (55, "D+", 1.5), (50, "D", 1.0), (0, "F", 0.0),
]


def grade_for(score: float):
    for low, letter, points in SCALE:
        if score >= low:
            return letter, points
    return "F", 0.0


@app.post("/students", status_code=201)
def create_student(data: StudentIn):
    name = data.name.strip()
    if not name:
        raise HTTPException(422, "Name must not be blank")
    with Session(engine) as s:
        st = Student(name=name)
        s.add(st)
        s.commit()
        s.refresh(st)
        return st.model_dump()


@app.get("/students")
def list_students():
    with Session(engine) as s:
        return [x.model_dump() for x in s.exec(select(Student).order_by(Student.id))]


@app.get("/students/{student_id}")
def get_student(student_id: int):
    with Session(engine) as s:
        st = s.get(Student, student_id)
        if not st:
            raise HTTPException(404, "Student not found")
        return st.model_dump()


@app.post("/courses", status_code=201)
def create_course(data: CourseIn):
    name = data.name.strip()
    if not name:
        raise HTTPException(422, "Name must not be blank")
    with Session(engine) as s:
        c = Course(name=name, credit_hours=data.credit_hours)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c.model_dump()


@app.get("/courses")
def list_courses():
    with Session(engine) as s:
        return [x.model_dump() for x in s.exec(select(Course).order_by(Course.id))]


@app.get("/courses/{course_id}")
def get_course(course_id: int):
    with Session(engine) as s:
        c = s.get(Course, course_id)
        if not c:
            raise HTTPException(404, "Course not found")
        return c.model_dump()


@app.post("/scores")
def enter_score(data: ScoreIn):
    with Session(engine) as s:
        if not s.get(Student, data.student_id):
            raise HTTPException(404, "Student not found")
        if not s.get(Course, data.course_id):
            raise HTTPException(404, "Course not found")
        existing = s.exec(
            select(Score).where(Score.student_id == data.student_id, Score.course_id == data.course_id)
        ).first()
        if existing:
            existing.score = data.score
            sc = existing
        else:
            sc = Score(student_id=data.student_id, course_id=data.course_id, score=data.score)
        s.add(sc)
        s.commit()
        s.refresh(sc)
        letter, points = grade_for(sc.score)
        return {**sc.model_dump(), "grade": letter, "grade_points": points}


@app.get("/students/{student_id}/results")
def student_results(student_id: int):
    with Session(engine) as s:
        st = s.get(Student, student_id)
        if not st:
            raise HTTPException(404, "Student not found")
        rows = s.exec(
            select(Score, Course).where(Score.student_id == student_id, Score.course_id == Course.id)
            .order_by(Course.id)
        ).all()
        results = []
        total_points = 0.0
        total_credits = 0
        for sc, c in rows:
            letter, points = grade_for(sc.score)
            results.append({
                "course_id": c.id,
                "course_name": c.name,
                "credit_hours": c.credit_hours,
                "score": sc.score,
                "grade": letter,
                "grade_points": points,
            })
            total_points += points * c.credit_hours
            total_credits += c.credit_hours
        gpa = round(total_points / total_credits, 2) if total_credits else None
        return {
            "student": st.model_dump(),
            "results": results,
            "total_credit_hours": total_credits,
            "gpa": gpa,
        }
