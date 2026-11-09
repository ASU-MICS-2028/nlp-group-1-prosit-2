import math
import threading
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="Trotro Routes and Fares")

_lock = threading.Lock()
_routes = {}
_next_id = 1

MAX_FARE = 10000.0
MAX_NAME = 100


class RouteIn(BaseModel):
    from_stop: str
    to_stop: str
    fare: float


class FareUpdate(BaseModel):
    fare: float


def _clean_stop(value, field):
    if value is None:
        raise HTTPException(status_code=422, detail=f"{field} is required")
    v = " ".join(str(value).split())
    if not v:
        raise HTTPException(status_code=422, detail=f"{field} must not be empty")
    if len(v) > MAX_NAME:
        raise HTTPException(status_code=422, detail=f"{field} is too long (max {MAX_NAME} characters)")
    return v


def _clean_fare(fare):
    try:
        f = float(fare)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="fare must be a number")
    if not math.isfinite(f):
        raise HTTPException(status_code=422, detail="fare must be a real number")
    if f <= 0:
        raise HTTPException(status_code=422, detail="fare must be greater than 0 cedis")
    if f > MAX_FARE:
        raise HTTPException(status_code=422, detail=f"fare must not exceed {MAX_FARE:.0f} cedis")
    return round(f, 2)


def _key(s):
    return s.casefold()


def _find(from_stop, to_stop):
    for r in _routes.values():
        if _key(r["from_stop"]) == _key(from_stop) and _key(r["to_stop"]) == _key(to_stop):
            return r
    return None


@app.get("/")
def home():
    return {"message": "Trotro routes and fares service", "endpoints": ["POST /routes", "GET /routes", "GET /routes/{id}", "PATCH /routes/{id}", "GET /fare?from_stop=..&to_stop=.."]}


@app.post("/routes", status_code=201)
def add_route(route: RouteIn):
    global _next_id
    f = _clean_stop(route.from_stop, "from_stop")
    t = _clean_stop(route.to_stop, "to_stop")
    if _key(f) == _key(t):
        raise HTTPException(status_code=422, detail="from_stop and to_stop must be different stops")
    fare = _clean_fare(route.fare)
    with _lock:
        if _find(f, t):
            raise HTTPException(status_code=409, detail=f"A route from {f} to {t} already exists; change its fare instead")
        rid = _next_id
        _next_id += 1
        rec = {"id": rid, "from_stop": f, "to_stop": t, "fare": fare, "currency": "GHS"}
        _routes[rid] = rec
        return dict(rec)


@app.get("/routes")
def list_routes():
    with _lock:
        return [dict(r) for r in sorted(_routes.values(), key=lambda r: r["id"])]


@app.get("/routes/{route_id}")
def get_route(route_id: int):
    with _lock:
        r = _routes.get(route_id)
        if not r:
            raise HTTPException(status_code=404, detail="Route not found")
        return dict(r)


@app.patch("/routes/{route_id}")
def change_fare(route_id: int, update: FareUpdate):
    fare = _clean_fare(update.fare)
    with _lock:
        r = _routes.get(route_id)
        if not r:
            raise HTTPException(status_code=404, detail="Route not found")
        old = r["fare"]
        r["fare"] = fare
        out = dict(r)
        out["previous_fare"] = old
        return out


@app.put("/routes/{route_id}/fare")
def change_fare_put(route_id: int, update: FareUpdate):
    return change_fare(route_id, update)


@app.get("/fare")
def lookup_fare(from_stop: str = Query(...), to_stop: str = Query(...)):
    f = _clean_stop(from_stop, "from_stop")
    t = _clean_stop(to_stop, "to_stop")
    if _key(f) == _key(t):
        raise HTTPException(status_code=422, detail="from_stop and to_stop must be different stops")
    with _lock:
        r = _find(f, t)
        reverse = False
        if not r:
            r = _find(t, f)
            reverse = True
        if not r:
            raise HTTPException(status_code=404, detail=f"No route found between {f} and {t}")
        return {"from_stop": f, "to_stop": t, "fare": r["fare"], "currency": "GHS", "route_id": r["id"], "based_on_reverse_route": reverse}
