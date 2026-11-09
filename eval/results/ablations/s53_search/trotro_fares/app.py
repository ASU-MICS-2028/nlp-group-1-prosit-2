from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///trotro.db", connect_args={"check_same_thread": False})


class Route(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stop_a: str
    stop_b: str
    fare: float


class RouteIn(BaseModel):
    stop_a: str
    stop_b: str
    fare: float = PField(gt=0)

    @field_validator("stop_a", "stop_b")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("stop name must not be empty")
        return v


class FareIn(BaseModel):
    fare: float = PField(gt=0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Trotro routes and fares", lifespan=lifespan)


def same(a: str, b: str) -> bool:
    return a.strip().casefold() == b.strip().casefold()


def find_route(session: Session, x: str, y: str) -> Optional[Route]:
    for r in session.exec(select(Route)).all():
        if (same(r.stop_a, x) and same(r.stop_b, y)) or (same(r.stop_a, y) and same(r.stop_b, x)):
            return r
    return None


@app.post("/routes", status_code=201)
def add_route(data: RouteIn):
    if same(data.stop_a, data.stop_b):
        raise HTTPException(400, "A route must go between two different stops")
    with Session(engine) as session:
        if find_route(session, data.stop_a, data.stop_b):
            raise HTTPException(409, "This route already exists; change its fare instead")
        route = Route(stop_a=data.stop_a, stop_b=data.stop_b, fare=round(data.fare, 2))
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
        if route is None:
            raise HTTPException(404, "No direct route found between these stops")
        return {"from": from_stop.strip(), "to": to_stop.strip(), "fare": route.fare, "route_id": route.id}


@app.patch("/routes/{route_id}")
def change_fare(route_id: int, data: FareIn):
    with Session(engine) as session:
        route = session.get(Route, route_id)
        if route is None:
            raise HTTPException(404, "Route not found")
        route.fare = round(data.fare, 2)
        session.add(route)
        session.commit()
        session.refresh(route)
        return route
