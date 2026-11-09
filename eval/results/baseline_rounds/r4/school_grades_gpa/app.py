from threading import Lock
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="College Results Service")

_lock = Lock()
students = {}  # student_id -> dict
courses = {}   # code -> dict
scores = {}    # (student_id, code) -> float

# Grading scale (score lower bound, grade, grade point)
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
    for low, letter, point in GRADE_SCALE:
        if score >= low:
            return letter, point
    return "F", 0.0


def norm(s: str) -> str:
    return s.strip().upper()


class StudentIn(BaseModel):
    student_id: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)

    @field_validator("student_id", "name")
    @classmethod
    def not_blank(cls, v: str):
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class CourseIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    title: str = Field(min_length=1, max_length=200)
    credits: int = Field(default=3, ge=1, le=20)

    @field_validator("code", "title")
    @classmethod
    def not_blank(cls, v: str):
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class ScoreValue(BaseModel):
    score: float = Field(ge=0, le=100, allow_inf_nan=False)

    @field_validator("score", mode="before")
    @classmethod
    def no_bool(cls, v):
        if isinstance(v, bool):
            raise ValueError("score must be a number")
        return v


class ScoreIn(ScoreValue):
    student_id: str = Field(min_length=1)
    course_code: str = Field(min_length=1)


def _get_student(sid: str):
    key = norm(sid)
    if key not in students:
        raise HTTPException(status_code=404, detail=f"Student '{sid}' not found")
    return key


def _get_course(code: str):
    key = norm(code)
    if key not in courses:
        raise HTTPException(status_code=404, detail=f"Course '{code}' not found")
    return key


@app.get("/")
def root():
    return {"service": "College Results Service", "grading_scale": [
        {"min_score": low, "grade": g, "grade_point": p} for low, g, p in GRADE_SCALE]}


@app.post("/students", status_code=201)
def create_student(body: StudentIn):
    key = norm(body.student_id)
    with _lock:
        if key in students:
            raise HTTPException(status_code=409, detail="A student with this ID already exists")
        students[key] = {"student_id": body.student_id, "name": body.name}
        return students[key]


@app.get("/students")
def list_students():
    return list(students.values())


@app.get("/students/{student_id}")
def get_student(student_id: str):
    return students[_get_student(student_id)]


@app.post("/courses", status_code=201)
def create_course(body: CourseIn):
    key = norm(body.code)
    with _lock:
        if key in courses:
            raise HTTPException(status_code=409, detail="A course with this code already exists")
        courses[key] = {"code": key, "title": body.title, "credits": body.credits}
        return courses[key]


@app.get("/courses")
def list_courses():
    return list(courses.values())


@app.get("/courses/{code}")
def get_course(code: str):
    return courses[_get_course(code)]


def _record(student_id: str, course_code: str, score: float):
    with _lock:
        skey = _get_student(student_id)
        ckey = _get_course(course_code)
        replaced = (skey, ckey) in scores
        previous = scores.get((skey, ckey))
        scores[(skey, ckey)] = float(score)
    letter, point = grade_for(score)
    return {
        "student_id": students[skey]["student_id"],
        "course_code": ckey,
        "score": float(score),
        "grade": letter,
        "grade_point": point,
        "replaced_previous": replaced,
        "previous_score": previous,
    }


@app.post("/scores")
def enter_score(body: ScoreIn):
    return _record(body.student_id, body.course_code, body.score)


@app.put("/students/{student_id}/scores/{course_code}")
def put_score(student_id: str, course_code: str, body: ScoreValue):
    return _record(student_id, course_code, body.score)


@app.get("/courses/{code}/scores")
def course_scores(code: str):
    ckey = _get_course(code)
    out = []
    for (s, c), sc in scores.items():
        if c == ckey:
            g, p = grade_for(sc)
            out.append({"student_id": students[s]["student_id"], "name": students[s]["name"],
                        "score": sc, "grade": g, "grade_point": p})
    return {"course": courses[ckey], "scores": out}


@app.get("/students/{student_id}/results")
def student_results(student_id: str):
    skey = _get_student(student_id)
    results = []
    total_credits = 0
    total_points = 0.0
    for (s, c), sc in sorted(scores.items(), key=lambda kv: kv[0][1]):
        if s != skey:
            continue
        course = courses[c]
        g, p = grade_for(sc)
        results.append({
            "course_code": c,
            "course_title": course["title"],
            "credits": course["credits"],
            "score": sc,
            "grade": g,
            "grade_point": p,
        })
        total_credits += course["credits"]
        total_points += p * course["credits"]
    gpa = round(total_points / total_credits, 2) if total_credits else None
    return {
        "student": students[skey],
        "results": results,
        "total_credits": total_credits,
        "gpa": gpa,
    }
