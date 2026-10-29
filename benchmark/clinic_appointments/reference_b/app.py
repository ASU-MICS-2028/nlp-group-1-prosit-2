# Second correct backend for clinic_appointments: other valid choices than reference/
# (text ids, 200 on create, 422 for a taken slot, cancel returns the removed appointment, other names and paths).
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
physicians, visits = {}, {}


class PhysicianIn(BaseModel):
    doctor_name: str
    speciality: str


class VisitIn(BaseModel):
    physician: str
    who: str
    on: str
    at: str


@app.post("/physicians")
def add_physician(p: PhysicianIn):
    doc = {"ref": uuid4().hex, **p.model_dump()}
    physicians[doc["ref"]] = doc
    return doc


@app.get("/physicians")
def all_physicians():
    return list(physicians.values())


@app.post("/visits")
def add_visit(v: VisitIn):
    if v.physician not in physicians:
        raise HTTPException(422, "Unknown doctor")
    if any(x["physician"] == v.physician and x["on"] == v.on and x["at"] == v.at for x in visits.values()):
        raise HTTPException(422, "Slot taken")
    visit = {"ref": uuid4().hex, **v.model_dump()}
    visits[visit["ref"]] = visit
    return visit


@app.get("/physicians/{ref}/visits")
def physician_visits(ref: str, on: str):
    return [x for x in visits.values() if x["physician"] == ref and x["on"] == on]


@app.delete("/visits/{ref}")
def remove_visit(ref: str):
    if ref not in visits:
        raise HTTPException(404, "Unknown appointment")
    return visits.pop(ref)
