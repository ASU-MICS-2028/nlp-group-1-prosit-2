from datetime import date
from threading import Lock
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Church Event Sign-ups")

_lock = Lock()
_events: Dict[int, dict] = {}
_signups: Dict[int, List[dict]] = {}
_next_event_id = 1
_next_signup_id = 1


class EventIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    date: date
    capacity: int = Field(..., ge=1)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


class SignupIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=1, max_length=50)

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


def _event_view(ev: dict) -> dict:
    count = len(_signups.get(ev["id"], []))
    return {
        "id": ev["id"],
        "name": ev["name"],
        "date": ev["date"].isoformat(),
        "capacity": ev["capacity"],
        "signed_up": count,
        "spots_left": max(ev["capacity"] - count, 0),
        "is_full": count >= ev["capacity"],
    }


def _get_event(event_id: int) -> dict:
    ev = _events.get(event_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return ev


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
        current = _signups[event_id]
        if len(current) >= ev["capacity"]:
            raise HTTPException(status_code=409, detail="Sorry, this event is full")
        s = {"id": _next_signup_id, "event_id": event_id, "name": data.name, "phone": data.phone}
        _next_signup_id += 1
        current.append(s)
        return s


@app.get("/events/{event_id}/signups")
def list_signups(event_id: int):
    with _lock:
        _get_event(event_id)
        return list(_signups[event_id])
