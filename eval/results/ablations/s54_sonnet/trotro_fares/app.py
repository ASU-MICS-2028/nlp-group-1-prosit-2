from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import SQLModel, Field, Session, create_engine, select

engine = create_engine("sqlite:///routes.db", connect_args={"check_same_thread": False})


class Route(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    origin: str
    destination: str
    fare: float
    pair_key: str = Field(index=True, unique=True)


def make_key(a: str, b: str) -> str:
    return "|".join(sorted([a.strip().lower(), b.strip().lower()]))


class RouteIn(BaseModel):
    origin: str
    destination: str
    fare: float

    @field_validator("origin", "destination")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("fare")
    @classmethod
    def positive(cls, v):
        if not v > 0 or v == float("inf"):
            raise ValueError("fare must be greater than 0")
        return v


class FareUpdate(BaseModel):
    fare: float

    @field_validator("fare")
    @classmethod
    def positive(cls, v):
        if not v > 0 or v == float("inf"):
            raise ValueError("fare must be greater than 0")
        return v


def out(r: Route):
    return {"id": r.id, "origin": r.origin, "destination": r.destination, "fare": r.fare}


app = FastAPI()
SQLModel.metadata.create_all(engine)


@app.post("/routes", status_code=201)
def add_route(body: RouteIn):
    if body.origin.lower() == body.destination.lower():
        raise HTTPException(422, "origin and destination must differ")
    key = make_key(body.origin, body.destination)
    with Session(engine) as s:
        if s.exec(select(Route).where(Route.pair_key == key)).first():
            raise HTTPException(409, "route already exists")
        r = Route(origin=body.origin, destination=body.destination, fare=body.fare, pair_key=key)
        s.add(r)
        s.commit()
        s.refresh(r)
        return out(r)


@app.get("/routes")
def list_routes():
    with Session(engine) as s:
        return [out(r) for r in s.exec(select(Route).order_by(Route.id)).all()]


@app.get("/fare")
def get_fare(origin: str, destination: str):
    with Session(engine) as s:
        r = s.exec(select(Route).where(Route.pair_key == make_key(origin, destination))).first()
        if not r:
            raise HTTPException(404, "route not found")
        return {"origin": origin.strip(), "destination": destination.strip(), "fare": r.fare}


@app.put("/routes/{route_id}")
@app.patch("/routes/{route_id}")
def update_fare(route_id: int, body: FareUpdate):
    with Session(engine) as s:
        r = s.get(Route, route_id)
        if not r:
            raise HTTPException(404, "route not found")
        r.fare = body.fare
        s.add(r)
        s.commit()
        s.refresh(r)
        return out(r)
