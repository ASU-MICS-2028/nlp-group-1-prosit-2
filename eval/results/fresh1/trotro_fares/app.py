from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///trotro.db", connect_args={"check_same_thread": False})


class Route(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stop_a: str
    stop_b: str
    fare: float


class RouteCreate(SQLModel):
    stop_a: str
    stop_b: str
    fare: float

    @field_validator("stop_a", "stop_b")
    @classmethod
    def stop_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("stop name must not be empty")
        return v

    @field_validator("fare")
    @classmethod
    def fare_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("fare must be greater than 0")
        return round(v, 2)


class FareUpdate(SQLModel):
    fare: float

    @field_validator("fare")
    @classmethod
    def fare_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("fare must be greater than 0")
        return round(v, 2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Trotro Routes and Fares", lifespan=lifespan)


def find_route(session: Session, a: str, b: str) -> Optional[Route]:
    a, b = a.strip().lower(), b.strip().lower()
    for r in session.exec(select(Route)).all():
        x, y = r.stop_a.lower(), r.stop_b.lower()
        if (x == a and y == b) or (x == b and y == a):
            return r
    return None


@app.post("/routes", status_code=201, response_model=Route)
def add_route(data: RouteCreate):
    if data.stop_a.lower() == data.stop_b.lower():
        raise HTTPException(400, "A route must go between two different stops")
    with Session(engine) as session:
        if find_route(session, data.stop_a, data.stop_b):
            raise HTTPException(409, "This route already exists (in one direction or the other)")
        route = Route(stop_a=data.stop_a, stop_b=data.stop_b, fare=data.fare)
        session.add(route)
        session.commit()
        session.refresh(route)
        return route


@app.get("/routes", response_model=list[Route])
def list_routes():
    with Session(engine) as session:
        return session.exec(select(Route).order_by(Route.id)).all()


@app.get("/fare")
def get_fare(from_stop: str = Query(..., alias="from"), to_stop: str = Query(..., alias="to")):
    with Session(engine) as session:
        route = find_route(session, from_stop, to_stop)
        if not route:
            raise HTTPException(404, "No direct route found between these stops")
        return {"from": from_stop.strip(), "to": to_stop.strip(), "fare": route.fare, "route_id": route.id}


@app.patch("/routes/{route_id}", response_model=Route)
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
