import math
from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation
from typing import Any, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///trotro.db", connect_args={"check_same_thread": False})


class Route(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stop_a: str
    stop_b: str
    fare: float


def check_fare(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("fare must be a number in cedis")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("fare must be a real number")
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("fare must be a number in cedis")
    if d <= 0:
        raise ValueError("fare must be above zero")
    if d != d.quantize(Decimal("0.01")):
        raise ValueError("fare can have at most two decimal places (pesewas)")
    return float(d)


def check_stop(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("stop name is required")
    return value.strip()


class RouteCreate(BaseModel):
    stop_a: Any
    stop_b: Any
    fare: Any

    @field_validator("stop_a", "stop_b")
    @classmethod
    def _stop(cls, v):
        return check_stop(v)

    @field_validator("fare")
    @classmethod
    def _fare(cls, v):
        return check_fare(v)


class FareUpdate(BaseModel):
    fare: Any

    @field_validator("fare")
    @classmethod
    def _fare(cls, v):
        return check_fare(v)


class RouteOut(BaseModel):
    id: int
    stop_a: str
    stop_b: str
    fare: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Trotro Routes and Fares", lifespan=lifespan)


def get_session():
    with Session(engine) as session:
        yield session


def find_route(session: Session, a: str, b: str) -> Optional[Route]:
    a, b = a.strip().lower(), b.strip().lower()
    stmt = select(Route).where(
        ((func.lower(Route.stop_a) == a) & (func.lower(Route.stop_b) == b))
        | ((func.lower(Route.stop_a) == b) & (func.lower(Route.stop_b) == a))
    )
    return session.exec(stmt).first()


@app.post("/routes", response_model=RouteOut, status_code=201)
def add_route(data: RouteCreate, session: Session = Depends(get_session)):
    if data.stop_a.lower() == data.stop_b.lower():
        raise HTTPException(422, "The two stops must be different places")
    if find_route(session, data.stop_a, data.stop_b):
        raise HTTPException(409, "A route between these two stops already exists")
    route = Route(stop_a=data.stop_a, stop_b=data.stop_b, fare=data.fare)
    session.add(route)
    session.commit()
    session.refresh(route)
    return route


@app.get("/routes", response_model=List[RouteOut])
def list_routes(session: Session = Depends(get_session)):
    return session.exec(select(Route).order_by(Route.id)).all()


@app.get("/fare")
def get_fare(
    from_stop: str = Query(..., alias="from"),
    to_stop: str = Query(..., alias="to"),
    session: Session = Depends(get_session),
):
    if not from_stop.strip() or not to_stop.strip():
        raise HTTPException(422, "Both stops are required")
    route = find_route(session, from_stop, to_stop)
    if not route:
        raise HTTPException(404, "No direct route found between these stops")
    return {
        "from": from_stop.strip(),
        "to": to_stop.strip(),
        "fare": route.fare,
        "route_id": route.id,
    }


@app.patch("/routes/{route_id}", response_model=RouteOut)
def change_fare(route_id: int, data: FareUpdate, session: Session = Depends(get_session)):
    route = session.get(Route, route_id)
    if not route:
        raise HTTPException(404, "Route not found")
    route.fare = data.fare
    session.add(route)
    session.commit()
    session.refresh(route)
    return route
