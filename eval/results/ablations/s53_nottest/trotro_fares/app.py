from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, func, or_, and_

engine = create_engine("sqlite:///trotro.db", connect_args={"check_same_thread": False})


class Route(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stop_a: str
    stop_b: str
    fare: float


class RouteCreate(BaseModel):
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


class FareUpdate(BaseModel):
    fare: float = PField(gt=0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Trotro Routes and Fares", lifespan=lifespan)


def find_route(session: Session, a: str, b: str) -> Optional[Route]:
    a, b = a.strip().lower(), b.strip().lower()
    stmt = select(Route).where(
        or_(
            and_(func.lower(Route.stop_a) == a, func.lower(Route.stop_b) == b),
            and_(func.lower(Route.stop_a) == b, func.lower(Route.stop_b) == a),
        )
    )
    return session.exec(stmt).first()


@app.post("/routes", status_code=201)
def add_route(data: RouteCreate):
    if data.stop_a.lower() == data.stop_b.lower():
        raise HTTPException(400, "A route must go between two different stops")
    with Session(engine) as session:
        if find_route(session, data.stop_a, data.stop_b):
            raise HTTPException(409, "A route between these two stops already exists")
        route = Route(stop_a=data.stop_a, stop_b=data.stop_b, fare=data.fare)
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
            raise HTTPException(404, "No direct route found between these stops")
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
