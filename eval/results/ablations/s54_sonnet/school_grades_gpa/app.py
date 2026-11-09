from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as F, Session, create_engine, select, UniqueConstraint

engine = create_engine("sqlite:///results.db", connect_args={"check_same_thread": False})


class Student(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    name: str


class Course(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    name: str
    credit_hours: int


class Score(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("student_id", "course_id"),)
    id: Optional[int] = F(default=None, primary_key=True)
    student_id: int = F(foreign_key="student.id")
    course_id: int = F(foreign_key="course.id")
    score: float


class StudentIn(BaseModel):
    name: str = Field(min_length=1)


class CourseIn(BaseModel):
    name: str = Field(min_length=1)
    credit_hours: int = Field(ge=1, le=6)


class ScoreIn(BaseModel):
    student_id: int
    course_id: int
    score: float = Field(ge=0, le=100)


SQLModel.metadata.create_all(engine)
app = FastAPI()


def grade(s: float):
    for low, g, p in [(80, "A", 4.0), (75, "B+", 3.5), (70, "B", 3.0), (65, "C+", 2.5),
                      (60, "C", 2.0), (55, "D+", 1.5), (50, "D", 1.0)]:
        if s >= low:
            return g, p
    return "F", 0.0


@app.post("/students", status_code=201)
def create_student(body: StudentIn):
    if not body.name.strip():
        raise HTTPException(422, "name required")
    with Session(engine) as s:
        st = Student(name=body.name)
        s.add(st)
        s.commit()
        s.refresh(st)
        return st


@app.get("/students")
def list_students():
    with Session(engine) as s:
        return s.exec(select(Student)).all()


@app.post("/courses", status_code=201)
def create_course(body: CourseIn):
    if not body.name.strip():
        raise HTTPException(422, "name required")
    with Session(engine) as s:
        c = Course(name=body.name, credit_hours=body.credit_hours)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


@app.get("/courses")
def list_courses():
    with Session(engine) as s:
        return s.exec(select(Course)).all()


@app.post("/scores")
def enter_score(body: ScoreIn):
    with Session(engine) as s:
        if not s.get(Student, body.student_id):
            raise HTTPException(404, "student not found")
        if not s.get(Course, body.course_id):
            raise HTTPException(404, "course not found")
        sc = s.exec(select(Score).where(Score.student_id == body.student_id,
                                        Score.course_id == body.course_id)).first()
        if sc:
            sc.score = body.score
        else:
            sc = Score(**body.model_dump())
        s.add(sc)
        s.commit()
        s.refresh(sc)
        g, p = grade(sc.score)
        return {"student_id": sc.student_id, "course_id": sc.course_id,
                "score": sc.score, "grade": g, "grade_points": p}


@app.get("/students/{student_id}/results")
def results(student_id: int):
    with Session(engine) as s:
        st = s.get(Student, student_id)
        if not st:
            raise HTTPException(404, "student not found")
        rows = s.exec(select(Score, Course).where(Score.student_id == student_id,
                                                  Score.course_id == Course.id)
                      .order_by(Course.id)).all()
        out = []
        pts = hrs = 0
        for sc, c in rows:
            g, p = grade(sc.score)
            out.append({"course_id": c.id, "course_name": c.name, "credit_hours": c.credit_hours,
                        "score": sc.score, "grade": g, "grade_points": p})
            pts += p * c.credit_hours
            hrs += c.credit_hours
        return {"student_id": st.id, "name": st.name, "results": out,
                "gpa": round(pts / hrs, 2) if hrs else None}
