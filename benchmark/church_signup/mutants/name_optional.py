# MUTANT name_optional: '    title: str = "Untitled"\n' instead of '    title: str\n'
# Reference backend for church_signup: proves the hidden tests are right.
# Deliberately uses different names (title, max_people, /church-events) to exercise ops.json translation.
from datetime import date

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
events, signups = {}, {}


class EventIn(BaseModel):
    title: str = "Untitled"
    date: date
    max_people: int


class PersonIn(BaseModel):
    name: str
    phone: str


def find(event_id):
    if event_id not in events:
        raise HTTPException(404, "No such event")
    return events[event_id]


@app.post("/church-events", status_code=201)
def create_event(e: EventIn):
    event = {"id": len(events) + 1, **e.model_dump()}
    events[event["id"]] = event
    signups[event["id"]] = []
    return event


@app.get("/church-events")
def list_events():
    return list(events.values())


@app.get("/church-events/{event_id}")
def get_event(event_id: int):
    return find(event_id)


@app.post("/church-events/{event_id}/signups", status_code=201)
def sign_up(event_id: int, p: PersonIn):
    event = find(event_id)
    if len(signups[event_id]) >= event["max_people"]:
        raise HTTPException(409, "This event is full")
    signups[event_id].append(p.model_dump())
    return p


@app.get("/church-events/{event_id}/signups")
def list_signups(event_id: int):
    find(event_id)
    return signups[event_id]
