from datetime import date
from threading import Lock
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Church Event Sign-ups")

_lock = Lock()
_events: Dict[int, dict] = {}
_signups: Dict[int, List[dict]] = {}
_next_event_id = 1
_next_signup_id = 1


class EventIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    date: date
    capacity: int = Field(..., ge=1, le=100000)


class SignupIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=3, max_length=40)


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


def _normalize_phone(phone: str) -> str:
    phone = phone.strip()
    allowed = set("0123456789+-() .")
    if not phone or any(c not in allowed for c in phone):
        raise HTTPException(status_code=422, detail="Phone number may only contain digits, spaces, +, -, ( and )")
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 3:
        raise HTTPException(status_code=422, detail="Phone number must contain at least 3 digits")
    return phone


@app.get("/")
def root():
    return {"message": "Church event sign-up service. See /docs for usage."}


@app.post("/events", status_code=201)
def create_event(data: EventIn):
    global _next_event_id
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Event name cannot be blank")
    with _lock:
        ev = {"id": _next_event_id, "name": name, "date": data.date, "capacity": data.capacity}
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
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name cannot be blank")
    phone = _normalize_phone(data.phone)
    phone_digits = "".join(c for c in phone if c.isdigit())
    with _lock:
        ev = _get_event(event_id)
        people = _signups[event_id]
        if len(people) >= ev["capacity"]:
            raise HTTPException(status_code=409, detail="Sorry, this event is full")
        for p in people:
            if "".join(c for c in p["phone"] if c.isdigit()) == phone_digits:
                raise HTTPException(status_code=409, detail="This phone number is already signed up for this event")
        s = {"id": _next_signup_id, "event_id": event_id, "name": name, "phone": phone}
        _next_signup_id += 1
        people.append(s)
        return {"signup": s, "event": _event_view(ev)}


@app.get("/events/{event_id}/signups")
def list_signups(event_id: int):
    with _lock:
        ev = _get_event(event_id)
        return {"event": _event_view(ev), "signups": list(_signups[event_id])}
