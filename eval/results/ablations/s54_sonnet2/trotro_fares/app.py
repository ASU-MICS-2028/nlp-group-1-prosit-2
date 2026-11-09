from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator, Field
from sqlmodel import Field as SField, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///./routes.db", connect_args={"check_same_thread": False})


class Route(SQLModel, table=True):
    id: Optional[int] = SField(default=None, primary_key=True)
    origin: str
    destination: str
    fare: float


class RouteIn(BaseModel):
    origin: str
    destination: str
    fare: float = Field(gt=0)

    @field_validator("origin", "destination")
    @classmethod
    def clean(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class FareUpdate(BaseModel):
    fare: float = Field(gt=0)


app = FastAPI()
SQLModel.metadata.create_all(engine)


def key(s: str) -> str:
    return " ".join(s.split()).lower()


def find(session, a, b):
    a, b = key(a), key(b)
    for r in session.exec(select(Route)).all():
        pair = (key(r.origin), key(r.destination))
        if pair == (a, b) or pair == (b, a):
            return r
    return None


@app.post("/routes", status_code=201)
def add_route(data: RouteIn):
    if key(data.origin) == key(data.destination):
        raise HTTPException(422, "Origin and destination must be different")
    with Session(engine) as s:
        if find(s, data.origin, data.destination):
            raise HTTPException(409, "Route already exists")
        r = Route(origin=data.origin, destination=data.destination, fare=data.fare)
        s.add(r)
        s.commit()
        s.refresh(r)
        return r


@app.get("/routes")
def list_routes():
    with Session(engine) as s:
        return s.exec(select(Route)).all()


@app.get("/fare")
def get_fare(origin: str, destination: str):
    with Session(engine) as s:
        r = find(s, origin, destination)
        if not r:
            raise HTTPException(404, "Route not found")
        return {"origin": origin.strip(), "destination": destination.strip(), "fare": r.fare}


@app.patch("/routes/{route_id}")
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
