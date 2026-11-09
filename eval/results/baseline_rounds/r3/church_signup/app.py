from datetime import date as Date, datetime, timezone
from threading import Lock
from typing import List, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Church Event Sign-ups")

_lock = Lock()
_events: Dict[int, dict] = {}
_signups: Dict[int, List[dict]] = {}
_next_event_id = 1
_next_signup_id = 1


class EventIn(BaseModel):
    name: str = Field(..., max_length=200)
    date: Date
    capacity: int = Field(..., ge=1, le=100000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class SignupIn(BaseModel):
    name: str = Field(..., max_length=200)
    phone: str = Field(..., max_length=50)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("phone must not be empty")
        allowed = set("0123456789+-() .")
        if any(c not in allowed for c in v):
            raise ValueError("phone may only contain digits, spaces and + - ( ) .")
        if sum(c.isdigit() for c in v) < 3:
            raise ValueError("phone must contain digits")
        return v


def _event_view(ev: dict) -> dict:
    taken = len(_signups.get(ev["id"], []))
    return {
        "id": ev["id"],
        "name": ev["name"],
        "date": ev["date"].isoformat(),
        "capacity": ev["capacity"],
        "signed_up": taken,
        "spots_left": max(ev["capacity"] - taken, 0),
        "is_full": taken >= ev["capacity"],
    }


def _get_event(event_id: int) -> dict:
    ev = _events.get(event_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return ev


@app.get("/")
def root():
    return {"message": "Church event sign-ups. See /docs for how to use it."}


@app.post("/events", status_code=201)
def create_event(data: EventIn):
    global _next_event_id
    with _lock:
        ev = {"id": _next_event_id, "name": data.name, "date": data.date, "capacity": data.capacity}
        _events[ev["id"]] = ev
        _signups[ev["id"]] = []
        _next_event_id += 1
        return _event_view(ev)


@app.get("/events")
def list_events():
    with _lock:
        evs = sorted(_events.values(), key=lambda e: (e["date"], e["id"]))
        return [_event_view(e) for e in evs]


@app.get("/events/{event_id}")
def get_event(event_id: int):
    with _lock:
        return _event_view(_get_event(event_id))


@app.post("/events/{event_id}/signups", status_code=201)
def sign_up(event_id: int, data: SignupIn):
    global _next_signup_id
    with _lock:
        ev = _get_event(event_id)
        people = _signups[event_id]
        if len(people) >= ev["capacity"]:
            raise HTTPException(status_code=409, detail="Sorry, this event is full")
        norm = "".join(c for c in data.phone if c.isdigit())
        for p in people:
            if "".join(c for c in p["phone"] if c.isdigit()) == norm and p["name"].lower() == data.name.lower():
                raise HTTPException(status_code=409, detail="This person is already signed up for this event")
        s = {
            "id": _next_signup_id,
            "event_id": event_id,
            "name": data.name,
            "phone": data.phone,
            "signed_up_at": datetime.now(timezone.utc).isoformat(),
        }
        _next_signup_id += 1
        people.append(s)
        return s


@app.get("/events/{event_id}/signups")
def list_signups(event_id: int):
    with _lock:
        _get_event(event_id)
        return list(_signups[event_id])
