from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Trotro Routes and Fares")


class RouteCreate(BaseModel):
    origin: str = Field(..., min_length=1, max_length=100, description="Starting stop, e.g. Circle")
    destination: str = Field(..., min_length=1, max_length=100, description="Ending stop, e.g. Madina")
    fare: float = Field(..., gt=0, le=10000, description="Fare in cedis")

    @field_validator("origin", "destination")
    @classmethod
    def clean_stop(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Stop name cannot be empty")
        return v

    @field_validator("fare")
    @classmethod
    def round_fare(cls, v: float) -> float:
        return round(v, 2)


class FareUpdate(BaseModel):
    fare: float = Field(..., gt=0, le=10000, description="New fare in cedis")

    @field_validator("fare")
    @classmethod
    def round_fare(cls, v: float) -> float:
        return round(v, 2)


class Route(BaseModel):
    id: int
    origin: str
    destination: str
    fare: float
    currency: str = "GHS"


_routes: Dict[int, Route] = {}
_next_id = 1
_lock = Lock()


def _key(a: str, b: str):
    # Routes are treated as two-way: Circle-Madina is the same route as Madina-Circle
    a = " ".join(a.split()).casefold()
    b = " ".join(b.split()).casefold()
    return tuple(sorted((a, b)))


def _find(a: str, b: str) -> Optional[Route]:
    k = _key(a, b)
    for r in _routes.values():
        if _key(r.origin, r.destination) == k:
            return r
    return None


@app.get("/")
def home():
    return {
        "message": "Trotro routes and fares",
        "endpoints": {
            "add route": "POST /routes",
            "list routes": "GET /routes",
            "one route": "GET /routes/{id}",
            "find fare": "GET /fare?from_stop=Circle&to_stop=Madina",
            "change fare": "PATCH /routes/{id}",
        },
    }


@app.post("/routes", response_model=Route, status_code=201)
def add_route(data: RouteCreate):
    global _next_id
    if data.origin.casefold() == data.destination.casefold():
        raise HTTPException(status_code=422, detail="Origin and destination must be different stops")
    with _lock:
        existing = _find(data.origin, data.destination)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"A route between {existing.origin} and {existing.destination} already exists (id {existing.id}). Change its fare instead.",
            )
        route = Route(id=_next_id, origin=data.origin, destination=data.destination, fare=data.fare)
        _routes[_next_id] = route
        _next_id += 1
        return route


@app.get("/routes", response_model=List[Route])
def list_routes(stop: Optional[str] = Query(None, description="Only show routes touching this stop")):
    routes = list(_routes.values())
    if stop:
        s = " ".join(stop.split()).casefold()
        routes = [r for r in routes if r.origin.casefold() == s or r.destination.casefold() == s]
    return sorted(routes, key=lambda r: r.id)


@app.get("/routes/{route_id}", response_model=Route)
def get_route(route_id: int):
    r = _routes.get(route_id)
    if not r:
        raise HTTPException(status_code=404, detail="Route not found")
    return r


@app.get("/fare")
def find_fare(
    from_stop: str = Query(..., min_length=1, description="Where you are starting"),
    to_stop: str = Query(..., min_length=1, description="Where you are going"),
):
    if not from_stop.strip() or not to_stop.strip():
        raise HTTPException(status_code=422, detail="Both stops are required")
    if _key(from_stop, to_stop)[0] == _key(from_stop, to_stop)[1]:
        raise HTTPException(status_code=422, detail="Start and end stops must be different")
    r = _find(from_stop, to_stop)
    if not r:
        raise HTTPException(
            status_code=404,
            detail=f"No route found between {from_stop.strip()} and {to_stop.strip()}",
        )
    return {
        "from": " ".join(from_stop.split()),
        "to": " ".join(to_stop.split()),
        "fare": r.fare,
        "currency": "GHS",
        "route_id": r.id,
    }


@app.patch("/routes/{route_id}", response_model=Route)
def change_fare(route_id: int, data: FareUpdate):
    with _lock:
        r = _routes.get(route_id)
        if not r:
            raise HTTPException(status_code=404, detail="Route not found")
        updated = r.model_copy(update={"fare": data.fare})
        _routes[route_id] = updated
        return updated
