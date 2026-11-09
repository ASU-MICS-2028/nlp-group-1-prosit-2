from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///results.db", connect_args={"check_same_thread": False})


class Student(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    student_number: str = SQLField(unique=True, index=True)
    full_name: str


class Course(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    code: str = SQLField(unique=True, index=True)
    title: str
    credit_hours: int


class Score(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    student_id: int = SQLField(foreign_key="student.id", index=True)
    course_id: int = SQLField(foreign_key="course.id", index=True)
    score: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="College Results", lifespan=lifespan)


class StudentIn(BaseModel):
    student_number: str = Field(min_length=1)
    full_name: str = Field(min_length=1)


class CourseIn(BaseModel):
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    credit_hours: int = Field(ge=1, le=6, strict=True)


class ScoreIn(BaseModel):
    score: float = Field(ge=0, le=100, allow_inf_nan=False)


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
    for minimum, letter, points in GRADES:
        if score >= minimum:
            return letter, points
    return "F", 0.0


def student_out(s: Student):
    return {"student_number": s.student_number, "full_name": s.full_name}


def course_out(c: Course):
    return {"code": c.code, "title": c.title, "credit_hours": c.credit_hours}


@app.post("/students", status_code=201)
def create_student(data: StudentIn):
    number = data.student_number.strip()
    name = data.full_name.strip()
    if not number or not name:
        raise HTTPException(422, "Student number and full name must not be blank.")
    with Session(engine) as session:
        if session.exec(select(Student).where(Student.student_number == number)).first():
            raise HTTPException(409, "That student number is already in use.")
        s = Student(student_number=number, full_name=name)
        session.add(s)
        session.commit()
        session.refresh(s)
        return student_out(s)


@app.get("/students")
def list_students():
    with Session(engine) as session:
        return [student_out(s) for s in session.exec(select(Student).order_by(Student.student_number)).all()]


@app.post("/courses", status_code=201)
def create_course(data: CourseIn):
    code = data.code.strip()
    title = data.title.strip()
    if not code or not title:
        raise HTTPException(422, "Course code and title must not be blank.")
    with Session(engine) as session:
        if session.exec(select(Course).where(Course.code == code)).first():
            raise HTTPException(409, "That course code is already in use.")
        c = Course(code=code, title=title, credit_hours=data.credit_hours)
        session.add(c)
        session.commit()
        session.refresh(c)
        return course_out(c)


@app.get("/courses")
def list_courses():
    with Session(engine) as session:
        return [course_out(c) for c in session.exec(select(Course).order_by(Course.code)).all()]


@app.put("/students/{student_number}/scores/{course_code}")
def enter_score(student_number: str, course_code: str, data: ScoreIn):
    with Session(engine) as session:
        student = session.exec(select(Student).where(Student.student_number == student_number)).first()
        if not student:
            raise HTTPException(404, "Student not registered.")
        course = session.exec(select(Course).where(Course.code == course_code)).first()
        if not course:
            raise HTTPException(404, "Course not registered.")
        existing = session.exec(
            select(Score).where(Score.student_id == student.id, Score.course_id == course.id)
        ).first()
        if existing:
            existing.score = data.score
            session.add(existing)
        else:
            session.add(Score(student_id=student.id, course_id=course.id, score=data.score))
        session.commit()
        letter, points = grade_for(data.score)
        return {
            "student_number": student.student_number,
            "course_code": course.code,
            "score": data.score,
            "grade": letter,
            "grade_points": points,
        }


@app.get("/students/{student_number}/results")
def student_results(student_number: str):
    with Session(engine) as session:
        student = session.exec(select(Student).where(Student.student_number == student_number)).first()
        if not student:
            raise HTTPException(404, "Student not registered.")
        rows = session.exec(
            select(Score, Course).where(Score.student_id == student.id, Score.course_id == Course.id).order_by(Course.code)
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
            "gpa": gpa,
        }
