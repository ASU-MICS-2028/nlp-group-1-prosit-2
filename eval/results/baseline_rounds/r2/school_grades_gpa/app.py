from threading import Lock
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="College Results System")

_lock = Lock()
students: Dict[str, dict] = {}
courses: Dict[str, dict] = {}
scores: Dict[Tuple[str, str], dict] = {}

# Grading scale (score -> letter, grade point)
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
    for minimum, letter, point in GRADE_SCALE:
        if score >= minimum:
            return letter, point
    return "F", 0.0


def _clean(v: str, what: str) -> str:
    v = (v or "").strip()
    if not v:
        raise ValueError(f"{what} must not be empty")
    return v


class StudentIn(BaseModel):
    student_id: str = Field(max_length=50)
    name: str = Field(max_length=200)

    @field_validator("student_id")
    @classmethod
    def _sid(cls, v):
        return _clean(v, "student_id").upper()

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        return _clean(v, "name")


class CourseIn(BaseModel):
    code: str = Field(max_length=50)
    title: str = Field(max_length=200)
    credits: int = Field(default=3, ge=1, le=20)

    @field_validator("code")
    @classmethod
    def _code(cls, v):
        return _clean(v, "code").upper()

    @field_validator("title")
    @classmethod
    def _title(cls, v):
        return _clean(v, "title")


class ScoreIn(BaseModel):
    student_id: str
    course_code: str
    score: float = Field(ge=0, le=100, allow_inf_nan=False)

    @field_validator("student_id")
    @classmethod
    def _sid(cls, v):
        return _clean(v, "student_id").upper()

    @field_validator("course_code")
    @classmethod
    def _cc(cls, v):
        return _clean(v, "course_code").upper()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _get_student(sid: str) -> dict:
    s = students.get(sid.strip().upper())
    if not s:
        raise HTTPException(404, "Student not found")
    return s


def _get_course(code: str) -> dict:
    c = courses.get(code.strip().upper())
    if not c:
        raise HTTPException(404, "Course not found")
    return c


@app.get("/")
def home():
    return {"message": "College Results System", "grading_scale": grading_scale()}


@app.get("/grading-scale")
def grading_scale():
    out = []
    upper = 100
    for minimum, letter, point in GRADE_SCALE:
        out.append({"grade": letter, "min_score": minimum, "max_score": upper, "grade_point": point})
        upper = minimum - 0.01
    return out


# ---------- Students ----------
@app.post("/students", status_code=201)
def create_student(body: StudentIn):
    with _lock:
        if body.student_id in students:
            raise HTTPException(409, "A student with this ID already exists")
        rec = {"student_id": body.student_id, "name": body.name, "registered_at": _now()}
        students[body.student_id] = rec
        return rec


@app.get("/students")
def list_students():
    return sorted(students.values(), key=lambda s: s["student_id"])


@app.get("/students/{student_id}")
def get_student(student_id: str):
    return _get_student(student_id)


# ---------- Courses ----------
@app.post("/courses", status_code=201)
def create_course(body: CourseIn):
    with _lock:
        if body.code in courses:
            raise HTTPException(409, "A course with this code already exists")
        rec = {"code": body.code, "title": body.title, "credits": body.credits, "created_at": _now()}
        courses[body.code] = rec
        return rec


@app.get("/courses")
def list_courses():
    return sorted(courses.values(), key=lambda c: c["code"])


@app.get("/courses/{code}")
def get_course(code: str):
    return _get_course(code)


@app.get("/courses/{code}/scores")
def course_scores(code: str):
    c = _get_course(code)
    out = []
    for (sid, cc), rec in scores.items():
        if cc == c["code"]:
            letter, point = grade_for(rec["score"])
            out.append({"student_id": sid, "name": students[sid]["name"], "score": rec["score"], "grade": letter, "grade_point": point, "updated_at": rec["updated_at"]})
    out.sort(key=lambda r: r["student_id"])
    return {"course": c, "scores": out}


# ---------- Scores ----------
def _save_score(body: ScoreIn):
    with _lock:
        _get_student(body.student_id)
        _get_course(body.course_code)
        key = (body.student_id, body.course_code)
        existing = scores.get(key)
        now = _now()
        rec = {
            "student_id": body.student_id,
            "course_code": body.course_code,
            "score": body.score,
            "entered_at": existing["entered_at"] if existing else now,
            "updated_at": now,
        }
        if existing:
            rec["previous_score"] = existing["score"]
        scores[key] = rec
        letter, point = grade_for(body.score)
        return {**rec, "grade": letter, "grade_point": point, "replaced_previous": existing is not None}


@app.post("/scores")
def enter_score(body: ScoreIn):
    return _save_score(body)


@app.put("/scores")
def update_score(body: ScoreIn):
    return _save_score(body)


@app.get("/scores")
def list_scores():
    out = []
    for rec in scores.values():
        letter, point = grade_for(rec["score"])
        out.append({**rec, "grade": letter, "grade_point": point})
    return out


# ---------- Results ----------
@app.get("/students/{student_id}/results")
def student_results(student_id: str):
    s = _get_student(student_id)
    results = []
    total_credits = 0
    total_points = 0.0
    for (sid, cc), rec in scores.items():
        if sid != s["student_id"]:
            continue
        c = courses[cc]
        letter, point = grade_for(rec["score"])
        results.append({
            "course_code": cc,
            "course_title": c["title"],
            "credits": c["credits"],
            "score": rec["score"],
            "grade": letter,
            "grade_point": point,
        })
        total_credits += c["credits"]
        total_points += point * c["credits"]
    results.sort(key=lambda r: r["course_code"])
    gpa: Optional[float] = round(total_points / total_credits, 2) if total_credits else None
    return {
        "student": s,
        "results": results,
        "courses_taken": len(results),
        "total_credits": total_credits,
        "gpa": gpa,
    }
