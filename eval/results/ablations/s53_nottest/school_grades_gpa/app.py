from typing import Optional, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField
from sqlmodel import SQLModel, Field, Session, create_engine, select

engine = create_engine("sqlite:///results.db", connect_args={"check_same_thread": False})


class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class Course(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str
    title: str
    credit_hours: int


class Score(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id", index=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    score: float


class StudentIn(BaseModel):
    name: str = PField(min_length=1)


class CourseIn(BaseModel):
    code: str = PField(min_length=1)
    title: str = PField(min_length=1)
    credit_hours: int = PField(ge=1, le=6)


class ScoreIn(BaseModel):
    student_id: int
    course_id: int
    score: float = PField(ge=0, le=100)


app = FastAPI()


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


SCALE = [
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
    for minimum, letter, points in SCALE:
        if score >= minimum:
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
        return s.exec(select(Student)).all()


@app.post("/courses", status_code=201)
def create_course(data: CourseIn):
    with Session(engine) as s:
        c = Course(code=data.code, title=data.title, credit_hours=data.credit_hours)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


@app.get("/courses")
def list_courses():
    with Session(engine) as s:
        return s.exec(select(Course)).all()


@app.post("/scores")
def enter_score(data: ScoreIn):
    with Session(engine) as s:
        if not s.get(Student, data.student_id):
            raise HTTPException(404, "Student not found")
        if not s.get(Course, data.course_id):
            raise HTTPException(404, "Course not found")
        existing = s.exec(
            select(Score).where(
                Score.student_id == data.student_id, Score.course_id == data.course_id
            )
        ).first()
        if existing:
            existing.score = data.score
            sc = existing
        else:
            sc = Score(student_id=data.student_id, course_id=data.course_id, score=data.score)
        s.add(sc)
        s.commit()
        s.refresh(sc)
        return sc


@app.get("/students/{student_id}/results")
def student_results(student_id: int):
    with Session(engine) as s:
        st = s.get(Student, student_id)
        if not st:
            raise HTTPException(404, "Student not found")
        scores = s.exec(select(Score).where(Score.student_id == student_id)).all()
        results = []
        total_points = 0.0
        total_credits = 0
        for sc in scores:
            c = s.get(Course, sc.course_id)
            letter, points = grade_for(sc.score)
            results.append({
                "course_id": c.id,
                "code": c.code,
                "title": c.title,
                "credit_hours": c.credit_hours,
                "score": sc.score,
                "grade": letter,
                "grade_point": points,
            })
            total_points += points * c.credit_hours
            total_credits += c.credit_hours
        gpa = round(total_points / total_credits, 2) if total_credits else None
        return {
            "student": {"id": st.id, "name": st.name},
            "results": results,
            "total_credit_hours": total_credits,
            "gpa": gpa,
        }
