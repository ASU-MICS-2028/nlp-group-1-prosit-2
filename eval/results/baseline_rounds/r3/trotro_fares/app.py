from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Trotro Routes and Fares")

_lock = Lock()
_routes: Dict[int, dict] = {}
_next_id = 1


def _clean_stop(v: str) -> str:
    if not isinstance(v, str):
        raise ValueError("stop name must be text")
    v = " ".join(v.split())
    if not v:
        raise ValueError("stop name cannot be empty")
    if len(v) > 100:
        raise ValueError("stop name is too long (max 100 characters)")
    return v


def _check_fare(v: float) -> float:
    if v is None:
        raise ValueError("fare is required")
    if v <= 0:
        raise ValueError("fare must be more than 0 cedis")
    if v > 10000:
        raise ValueError("fare is unrealistically high")
    if abs(round(v, 2) - v) > 1e-9:
        raise ValueError("fare can have at most 2 decimal places (pesewas)")
    return round(v, 2)


class RouteCreate(BaseModel):
    origin: str = Field(..., description="Starting stop, e.g. Circle")
    destination: str = Field(..., description="Ending stop, e.g. Madina")
    fare: float = Field(..., description="Fare in cedis")

    @field_validator("origin", "destination", mode="before")
    @classmethod
    def _stops(cls, v):
        return _clean_stop(v)

    @field_validator("fare")
    @classmethod
    def _fare(cls, v):
        return _check_fare(v)


class FareUpdate(BaseModel):
    fare: float = Field(..., description="New fare in cedis")

    @field_validator("fare")
    @classmethod
    def _fare(cls, v):
        return _check_fare(v)


def _key(a: str, b: str):
    return frozenset({a.lower(), b.lower()})


def _find(a: str, b: str) -> Optional[dict]:
    k = _key(a, b)
    for r in _routes.values():
        if _key(r["origin"], r["destination"]) == k:
            return r
    return None


@app.post("/routes", status_code=201)
def add_route(body: RouteCreate):
    global _next_id
    if body.origin.lower() == body.destination.lower():
        raise HTTPException(status_code=400, detail="Origin and destination must be different stops")
    with _lock:
        existing = _find(body.origin, body.destination)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"A route between {existing['origin']} and {existing['destination']} already exists (id {existing['id']}). Change its fare instead.",
            )
        route = {"id": _next_id, "origin": body.origin, "destination": body.destination, "fare": body.fare, "currency": "GHS"}
        _routes[_next_id] = route
        _next_id += 1
        return route


@app.get("/routes")
def list_routes() -> List[dict]:
    with _lock:
        return sorted(_routes.values(), key=lambda r: r["id"])


@app.get("/routes/{route_id}")
def get_route(route_id: int):
    with _lock:
        r = _routes.get(route_id)
    if not r:
        raise HTTPException(status_code=404, detail="Route not found")
    return r


@app.patch("/routes/{route_id}")
def change_fare(route_id: int, body: FareUpdate):
    with _lock:
        r = _routes.get(route_id)
        if not r:
            raise HTTPException(status_code=404, detail="Route not found")
        old = r["fare"]
        r["fare"] = body.fare
        return {**r, "previous_fare": old}


@app.get("/fare")
def fare_lookup(
    origin: str = Query(..., alias="from", description="Stop you are leaving from"),
    destination: str = Query(..., alias="to", description="Stop you are going to"),
):
    try:
        o = _clean_stop(origin)
        d = _clean_stop(destination)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if o.lower() == d.lower():
        raise HTTPException(status_code=400, detail="From and to must be different stops")
    with _lock:
        r = _find(o, d)
    if not r:
        raise HTTPException(status_code=404, detail=f"No route found between {o} and {d}")
    return {"from": o, "to": d, "fare": r["fare"], "currency": "GHS", "route_id": r["id"]}
