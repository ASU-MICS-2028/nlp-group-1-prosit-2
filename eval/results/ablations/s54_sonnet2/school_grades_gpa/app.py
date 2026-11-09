from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Field as SField, Session, SQLModel, create_engine, select


class Student(SQLModel, table=True):
    id: Optional[int] = SField(default=None, primary_key=True)
    name: str


class Course(SQLModel, table=True):
    id: Optional[int] = SField(default=None, primary_key=True)
    name: str
    credit_hours: int


class Result(SQLModel, table=True):
    student_id: int = SField(primary_key=True, foreign_key="student.id")
    course_id: int = SField(primary_key=True, foreign_key="course.id")
    score: float


class StudentIn(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if not v.strip():
            raise ValueError("name must not be empty")
        return v.strip()


class CourseIn(StudentIn):
    credit_hours: int = Field(ge=1, le=6)


class ScoreIn(BaseModel):
    score: float = Field(ge=0, le=100)


engine = create_engine("sqlite:///app.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)

app = FastAPI()


def grade_for(score: float):
    for low, g, p in [(80, "A", 4.0), (75, "B+", 3.5), (70, "B", 3.0), (65, "C+", 2.5),
                      (60, "C", 2.0), (55, "D+", 1.5), (50, "D", 1.0)]:
        if score >= low:
            return g, p
    return "F", 0.0


@app.post("/students", status_code=201)
def create_student(body: StudentIn):
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


@app.get("/students/{student_id}")
def get_student(student_id: int):
    with Session(engine) as s:
        st = s.get(Student, student_id)
        if not st:
            raise HTTPException(404, "Student not found")
        return st


@app.post("/courses", status_code=201)
def create_course(body: CourseIn):
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


@app.get("/courses/{course_id}")
def get_course(course_id: int):
    with Session(engine) as s:
        c = s.get(Course, course_id)
        if not c:
            raise HTTPException(404, "Course not found")
        return c


@app.put("/students/{student_id}/results/{course_id}")
def set_score(student_id: int, course_id: int, body: ScoreIn):
    with Session(engine) as s:
        if not s.get(Student, student_id):
            raise HTTPException(404, "Student not found")
        if not s.get(Course, course_id):
            raise HTTPException(404, "Course not found")
        r = s.get(Result, (student_id, course_id))
        if r:
            r.score = body.score
        else:
            r = Result(student_id=student_id, course_id=course_id, score=body.score)
        s.add(r)
        s.commit()
        grade, points = grade_for(body.score)
        return {"student_id": student_id, "course_id": course_id,
                "score": body.score, "grade": grade, "grade_points": points}


@app.get("/students/{student_id}/results")
def student_results(student_id: int):
    with Session(engine) as s:
        st = s.get(Student, student_id)
        if not st:
            raise HTTPException(404, "Student not found")
        rows = s.exec(select(Result, Course).where(
            Result.student_id == student_id, Result.course_id == Course.id)
            .order_by(Course.id)).all()
        results = []
        total_pts = 0.0
        total_hours = 0
        for r, c in rows:
            g, p = grade_for(r.score)
            results.append({"course_id": c.id, "course_name": c.name,
                            "credit_hours": c.credit_hours, "score": r.score,
                            "grade": g, "grade_points": p})
            total_pts += p * c.credit_hours
            total_hours += c.credit_hours
        gpa = round(total_pts / total_hours, 2) if total_hours else None
        return {"student_id": st.id, "name": st.name, "results": results, "gpa": gpa}
