# MUTANT gpa_unweighted: '    cgpa = round(sum(l["points"] for l in lines) / len(lines), 2) if lines else 0\n' instead of '    cgpa = round(weighted / credits, 2) if credits else 0\n'
# Reference backend for school_grades_gpa: proves the hidden tests are right.
# Deliberately uses different names (learners, subjects, credit_hours, mark, letter, points, cgpa) to exercise ops.json.
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()
learners, subjects, marks = {}, {}, {}
SCALE = [(80, "A", 4.0), (75, "B+", 3.5), (70, "B", 3.0), (65, "C+", 2.5),
         (60, "C", 2.0), (55, "D+", 1.5), (50, "D", 1.0), (0, "F", 0.0)]


class LearnerIn(BaseModel):
    full_name: str


class SubjectIn(BaseModel):
    title: str
    credit_hours: int = Field(ge=1, le=6)


class MarkIn(BaseModel):
    subject: int
    mark: int = Field(ge=0, le=100)


def grade(mark):
    return next((letter, points) for low, letter, points in SCALE if mark >= low)


def find(sid):
    if sid not in learners:
        raise HTTPException(404, "No such student")
    return learners[sid]


@app.post("/learners", status_code=201)
def create_learner(l: LearnerIn):
    learner = {"id": len(learners) + 1, **l.model_dump()}
    learners[learner["id"]] = learner
    return learner


@app.post("/subjects", status_code=201)
def create_subject(s: SubjectIn):
    subject = {"id": len(subjects) + 1, **s.model_dump()}
    subjects[subject["id"]] = subject
    return subject


@app.post("/learners/{sid}/marks", status_code=201)
def record_mark(sid: int, m: MarkIn):
    find(sid)
    if m.subject not in subjects:
        raise HTTPException(404, "No such course")
    marks[(sid, m.subject)] = m.mark
    return {"subject": m.subject, "mark": m.mark}


@app.get("/learners/{sid}/transcript")
def transcript(sid: int):
    find(sid)
    lines = []
    for key, mark in marks.items():
        if key[0] == sid:
            letter, points = grade(mark)
            lines.append({"subject": key[1], "mark": mark, "letter": letter, "points": points})
    credits = sum(subjects[l["subject"]]["credit_hours"] for l in lines)
    weighted = sum(l["points"] * subjects[l["subject"]]["credit_hours"] for l in lines)
    cgpa = round(sum(l["points"] for l in lines) / len(lines), 2) if lines else 0
    return {"cgpa": cgpa, "lines": lines}
