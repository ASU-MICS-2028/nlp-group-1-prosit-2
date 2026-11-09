from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import func, or_, and_
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///routes.db", connect_args={"check_same_thread": False})


class Route(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    origin: str
    destination: str
    fare: float


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
    def fare_ok(cls, v):
        if v < 0:
            raise ValueError("fare must not be negative")
        return v


class FareUpdate(BaseModel):
    fare: float

    @field_validator("fare")
    @classmethod
    def fare_ok(cls, v):
        if v < 0:
            raise ValueError("fare must not be negative")
        return v


app = FastAPI()
SQLModel.metadata.create_all(engine)


def find(session, a, b):
    a, b = a.strip().lower(), b.strip().lower()
    return session.exec(
        select(Route).where(
            or_(
                and_(func.lower(Route.origin) == a, func.lower(Route.destination) == b),
                and_(func.lower(Route.origin) == b, func.lower(Route.destination) == a),
            )
        )
    ).first()


@app.post("/routes", status_code=201)
def add_route(data: RouteIn):
    if data.origin.lower() == data.destination.lower():
        raise HTTPException(422, "Origin and destination must be different")
    with Session(engine) as s:
        if find(s, data.origin, data.destination):
            raise HTTPException(409, "A route between these stops already exists")
        r = Route(origin=data.origin, destination=data.destination, fare=data.fare)
        s.add(r)
        s.commit()
        s.refresh(r)
        return r


@app.get("/routes")
def list_routes():
    with Session(engine) as s:
        return s.exec(select(Route).order_by(Route.id)).all()


@app.get("/fare")
def get_fare(origin: str, destination: str):
    with Session(engine) as s:
        r = find(s, origin, destination)
        if not r:
            raise HTTPException(404, "Route not found")
        return {"origin": origin.strip(), "destination": destination.strip(), "fare": r.fare, "route_id": r.id}


@app.put("/routes/{route_id}")
def update_fare(route_id: int, data: FareUpdate):
    with Session(engine) as s:
        r = s.get(Route, route_id)
        if not r:
            raise HTTPException(404, "Route not found")
        r.fare = data.fare
        s.add(r)
        s.commit()
        s.refresh(r)
        return r
