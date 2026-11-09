from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, func

engine = create_engine("sqlite:///trotro.db", connect_args={"check_same_thread": False})


class Route(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    origin: str
    destination: str
    fare: float


class RouteCreate(BaseModel):
    origin: str
    destination: str
    fare: float

    @field_validator("origin", "destination")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("stop name must not be empty")
        return v

    @field_validator("fare")
    @classmethod
    def positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("fare must be more than 0 cedis")
        return round(v, 2)


class FareUpdate(BaseModel):
    fare: float

    @field_validator("fare")
    @classmethod
    def positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("fare must be more than 0 cedis")
        return round(v, 2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Trotro Routes and Fares", lifespan=lifespan)


def find_route(session: Session, a: str, b: str) -> Optional[Route]:
    a, b = a.strip().lower(), b.strip().lower()
    for o, d in ((a, b), (b, a)):
        r = session.exec(
            select(Route).where(func.lower(Route.origin) == o, func.lower(Route.destination) == d)
        ).first()
        if r:
            return r
    return None


@app.post("/routes", status_code=201)
def add_route(data: RouteCreate):
    if data.origin.lower() == data.destination.lower():
        raise HTTPException(400, "A route must go between two different stops")
    with Session(engine) as session:
        if find_route(session, data.origin, data.destination):
            raise HTTPException(409, "A route between these two stops already exists")
        route = Route(origin=data.origin, destination=data.destination, fare=data.fare)
        session.add(route)
        session.commit()
        session.refresh(route)
        return route


@app.get("/routes")
def list_routes():
    with Session(engine) as session:
        return session.exec(select(Route).order_by(Route.id)).all()


@app.get("/fare")
def get_fare(from_stop: str = Query(..., alias="from"), to_stop: str = Query(..., alias="to")):
    with Session(engine) as session:
        route = find_route(session, from_stop, to_stop)
        if not route:
            raise HTTPException(404, "No route found between these stops")
        return {"from": from_stop.strip(), "to": to_stop.strip(), "fare": route.fare, "route_id": route.id}


@app.patch("/routes/{route_id}")
def change_fare(route_id: int, data: FareUpdate):
    with Session(engine) as session:
        route = session.get(Route, route_id)
        if not route:
            raise HTTPException(404, "Route not found")
        route.fare = data.fare
        session.add(route)
        session.commit()
        session.refresh(route)
        return route
