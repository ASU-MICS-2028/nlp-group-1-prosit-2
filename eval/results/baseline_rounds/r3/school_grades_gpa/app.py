from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="College Results Service", version="1.0.0")

_lock = threading.Lock()

# Grading scale (score out of 100): (min score, grade letter, grade points)
GRADE_SCALE: List[Tuple[float, str, float]] = [
    (80, "A", 4.0),
    (75, "B+", 3.5),
    (70, "B", 3.0),
    (65, "C+", 2.5),
    (60, "C", 2.0),
    (55, "D+", 1.5),
    (50, "D", 1.0),
    (0, "F", 0.0),
]


def grade_for(score: float) -> Tuple[str, float]:
    for minimum, letter, points in GRADE_SCALE:
        if score >= minimum:
            return letter, points
    return "F", 0.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_student_id(value: str) -> str:
    return value.strip()


def _norm_course_code(value: str) -> str:
    return " ".join(value.strip().upper().split())


# ---------- Models ----------

class StudentIn(BaseModel):
    student_id: str = Field(..., min_length=1, max_length=50, description="Index / student number")
    name: str = Field(..., min_length=1, max_length=200)

    @field_validator("student_id", "name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class CourseIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=30)
    title: str = Field(..., min_length=1, max_length=200)
    credits: int = Field(3, ge=1, le=30, description="Credit hours used to weight the GPA")

    @field_validator("code", "title")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class ScoreIn(BaseModel):
    student_id: str = Field(..., min_length=1)
    course_code: str = Field(..., min_length=1)
    score: float = Field(..., ge=0, le=100, allow_inf_nan=False, description="Score out of 100")


class ScoreValue(BaseModel):
    score: float = Field(..., ge=0, le=100, allow_inf_nan=False, description="Score out of 100")


# ---------- Storage ----------

students: Dict[str, dict] = {}
courses: Dict[str, dict] = {}
# key: (student_id, course_code)
scores: Dict[Tuple[str, str], dict] = {}


def _get_student(student_id: str) -> dict:
    s = students.get(_norm_student_id(student_id))
    if s is None:
        raise HTTPException(status_code=404, detail=f"Student '{student_id}' is not registered")
    return s


def _get_course(code: str) -> dict:
    c = courses.get(_norm_course_code(code))
    if c is None:
        raise HTTPException(status_code=404, detail=f"Course '{code}' is not registered")
    return c


def _score_view(rec: dict) -> dict:
    course = courses[rec["course_code"]]
    letter, points = grade_for(rec["score"])
    return {
        "student_id": rec["student_id"],
        "course_code": rec["course_code"],
        "course_title": course["title"],
        "credits": course["credits"],
        "score": rec["score"],
        "grade": letter,
        "grade_points": points,
        "entered_at": rec["entered_at"],
        "updated_at": rec["updated_at"],
        "times_entered": rec["times_entered"],
    }


def _save_score(student_id: str, course_code: str, value: float) -> Tuple[dict, bool]:
    student = _get_student(student_id)
    course = _get_course(course_code)
    key = (student["student_id"], course["code"])
    now = _now()
    existing = scores.get(key)
    if existing:
        existing["previous_score"] = existing["score"]
        existing["score"] = float(value)
        existing["updated_at"] = now
        existing["times_entered"] += 1
        return existing, False
    rec = {
        "student_id": key[0],
        "course_code": key[1],
        "score": float(value),
        "previous_score": None,
        "entered_at": now,
        "updated_at": now,
        "times_entered": 1,
    }
    scores[key] = rec
    return rec, True


# ---------- Routes ----------

@app.get("/")
def home():
    return {
        "service": "College Results Service",
        "grading_scale": [
            {"minimum_score": m, "grade": g, "grade_points": p} for m, g, p in GRADE_SCALE
        ],
        "gpa": "Credit-weighted average of grade points over all courses the student has a score in",
    }


@app.get("/grading-scale")
def grading_scale():
    return [{"minimum_score": m, "grade": g, "grade_points": p} for m, g, p in GRADE_SCALE]


# Students
@app.post("/students", status_code=201)
def create_student(body: StudentIn):
    sid = _norm_student_id(body.student_id)
    with _lock:
        if sid in students:
            raise HTTPException(status_code=409, detail=f"Student '{sid}' is already registered")
        rec = {"student_id": sid, "name": body.name, "registered_at": _now()}
        students[sid] = rec
        return rec


@app.get("/students")
def list_students():
    with _lock:
        return sorted(students.values(), key=lambda s: s["student_id"])


@app.get("/students/{student_id}")
def get_student(student_id: str):
    with _lock:
        return _get_student(student_id)


@app.get("/students/{student_id}/results")
def student_results(student_id: str):
    with _lock:
        student = _get_student(student_id)
        sid = student["student_id"]
        rows = [_score_view(r) for (s, _), r in scores.items() if s == sid]
        rows.sort(key=lambda r: r["course_code"])
        total_credits = sum(r["credits"] for r in rows)
        total_points = sum(r["credits"] * r["grade_points"] for r in rows)
        gpa = round(total_points / total_credits, 2) if total_credits else None
        return {
            "student_id": sid,
            "name": student["name"],
            "results": rows,
            "courses_taken": len(rows),
            "total_credits": total_credits,
            "total_grade_points": round(total_points, 2),
            "gpa": gpa,
        }


# Courses
@app.post("/courses", status_code=201)
def create_course(body: CourseIn):
    code = _norm_course_code(body.code)
    with _lock:
        if code in courses:
            raise HTTPException(status_code=409, detail=f"Course '{code}' is already registered")
        rec = {"code": code, "title": body.title, "credits": body.credits, "registered_at": _now()}
        courses[code] = rec
        return rec


@app.get("/courses")
def list_courses():
    with _lock:
        return sorted(courses.values(), key=lambda c: c["code"])


@app.get("/courses/{code}")
def get_course(code: str):
    with _lock:
        return _get_course(code)


@app.get("/courses/{code}/scores")
def course_scores(code: str):
    with _lock:
        course = _get_course(code)
        rows = []
        for (sid, c), r in scores.items():
            if c == course["code"]:
                v = _score_view(r)
                v["student_name"] = students[sid]["name"]
                rows.append(v)
        rows.sort(key=lambda r: r["student_id"])
        return {"course": course, "scores": rows}


# Scores
@app.post("/scores")
def enter_score(body: ScoreIn):
    """Enter a score. If the student already has a score for the course, the new one replaces it."""
    with _lock:
        rec, created = _save_score(body.student_id, body.course_code, body.score)
        out = _score_view(rec)
        out["replaced_previous"] = not created
        out["previous_score"] = rec["previous_score"] if not created else None
        return out


@app.put("/students/{student_id}/scores/{course_code}")
def put_score(student_id: str, course_code: str, body: ScoreValue):
    with _lock:
        rec, created = _save_score(student_id, course_code, body.score)
        out = _score_view(rec)
        out["replaced_previous"] = not created
        out["previous_score"] = rec["previous_score"] if not created else None
        return out


@app.get("/students/{student_id}/scores/{course_code}")
def get_score(student_id: str, course_code: str):
    with _lock:
        student = _get_student(student_id)
        course = _get_course(course_code)
        rec = scores.get((student["student_id"], course["code"]))
        if rec is None:
            raise HTTPException(status_code=404, detail="No score entered for this student in this course")
        return _score_view(rec)


@app.get("/scores")
def list_scores():
    with _lock:
        return [_score_view(r) for r in sorted(scores.values(), key=lambda r: (r["student_id"], r["course_code"]))]


@app.delete("/students/{student_id}/scores/{course_code}")
def delete_score(student_id: str, course_code: str):
    with _lock:
        student = _get_student(student_id)
        course = _get_course(course_code)
        key = (student["student_id"], course["code"])
        if key not in scores:
            raise HTTPException(status_code=404, detail="No score entered for this student in this course")
        del scores[key]
        return {"deleted": True, "student_id": key[0], "course_code": key[1]}
