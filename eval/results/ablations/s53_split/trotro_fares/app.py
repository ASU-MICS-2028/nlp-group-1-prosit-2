from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///trotro.db", connect_args={"check_same_thread": False})


class Route(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    first_stop: str
    second_stop: str
    fare: float


def _check_fare(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError("fare must be a number")
    v = float(v)
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError("fare must be a real number")
    if v <= 0:
        raise ValueError("fare must be greater than zero")
    return v


class RouteCreate(BaseModel):
    first_stop: str
    second_stop: str
    fare: object

    @field_validator("first_stop", "second_stop")
    @classmethod
    def stop_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("stop name must not be empty")
        return v

    @field_validator("fare")
    @classmethod
    def fare_ok(cls, v):
        return _check_fare(v)


class FareUpdate(BaseModel):
    fare: object

    @field_validator("fare")
    @classmethod
    def fare_ok(cls, v):
        return _check_fare(v)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Trotro Routes and Fares", lifespan=lifespan)


def _same(a: str, b: str) -> bool:
    return a.strip().casefold() == b.strip().casefold()


def _find_route(session: Session, a: str, b: str) -> Optional[Route]:
    for r in session.exec(select(Route)).all():
        if (_same(r.first_stop, a) and _same(r.second_stop, b)) or (
            _same(r.first_stop, b) and _same(r.second_stop, a)
        ):
            return r
    return None


@app.post("/routes", status_code=201)
def add_route(data: RouteCreate):
    if _same(data.first_stop, data.second_stop):
        raise HTTPException(400, "The two stops must be different.")
    with Session(engine) as session:
        if _find_route(session, data.first_stop, data.second_stop):
            raise HTTPException(409, "A route between these two stops already exists.")
        route = Route(first_stop=data.first_stop, second_stop=data.second_stop, fare=data.fare)
        session.add(route)
        session.commit()
        session.refresh(route)
        return route.model_dump()


@app.get("/routes")
def list_routes():
    with Session(engine) as session:
        return [r.model_dump() for r in session.exec(select(Route).order_by(Route.id)).all()]


@app.get("/fare")
def get_fare(from_stop: str = Query(..., alias="from"), to_stop: str = Query(..., alias="to")):
    with Session(engine) as session:
        route = _find_route(session, from_stop, to_stop)
        if not route:
            raise HTTPException(404, "No route found between these stops.")
        return {"from": from_stop.strip(), "to": to_stop.strip(), "fare": route.fare, "route_id": route.id}


@app.patch("/routes/{route_id}")
def change_fare(route_id: int, data: FareUpdate):
    with Session(engine) as session:
        route = session.get(Route, route_id)
        if not route:
            raise HTTPException(404, "Route not found.")
        route.fare = data.fare
        session.add(route)
        session.commit()
        session.refresh(route)
        return route.model_dump()
