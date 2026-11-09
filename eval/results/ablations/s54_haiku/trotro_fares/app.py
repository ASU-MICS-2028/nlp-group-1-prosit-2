from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./trotro.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Route(SQLModel, table=True):
    """A direct route between two stops. One route serves both directions."""

    id: Optional[int] = SQLField(default=None, primary_key=True)
    from_stop: str
    to_stop: str
    fare: float


class RouteCreate(BaseModel):
    from_stop: str
    to_stop: str
    fare: float = Field(gt=0)

    @field_validator("from_stop", "to_stop")
    @classmethod
    def clean_stop(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("stop name must not be empty")
        return value


class FareUpdate(BaseModel):
    fare: float = Field(gt=0)


def normalize(name: str) -> str:
    return " ".join(name.split()).casefold()


def pair_key(a: str, b: str) -> frozenset:
    return frozenset({normalize(a), normalize(b)})


@asynccontextmanager
async def lifespan(_app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Trotro Routes and Fares", lifespan=lifespan)


def route_out(route: Route) -> dict:
    return {
        "id": route.id,
        "from_stop": route.from_stop,
        "to_stop": route.to_stop,
        "fare": route.fare,
    }


@app.post("/routes", status_code=201)
def add_route(data: RouteCreate):
    if normalize(data.from_stop) == normalize(data.to_stop):
        raise HTTPException(status_code=422, detail="from_stop and to_stop must be different")
    with Session(engine) as session:
        wanted = pair_key(data.from_stop, data.to_stop)
        for existing in session.exec(select(Route)).all():
            if pair_key(existing.from_stop, existing.to_stop) == wanted:
                raise HTTPException(
                    status_code=409,
                    detail="a route between these two stops already exists",
                )
        route = Route(from_stop=data.from_stop, to_stop=data.to_stop, fare=data.fare)
        session.add(route)
        session.commit()
        session.refresh(route)
        return route_out(route)


@app.get("/routes")
def list_routes():
    with Session(engine) as session:
        routes = session.exec(select(Route).order_by(Route.id)).all()
        return [route_out(r) for r in routes]


@app.get("/fare")
def find_fare(from_stop: str, to_stop: str):
    wanted = pair_key(from_stop, to_stop)
    if len(wanted) < 2:
        raise HTTPException(status_code=404, detail="no direct route found between these stops")
    with Session(engine) as session:
        for route in session.exec(select(Route).order_by(Route.id)).all():
            if pair_key(route.from_stop, route.to_stop) == wanted:
                return {
                    "route_id": route.id,
                    "from_stop": from_stop.strip(),
                    "to_stop": to_stop.strip(),
                    "fare": route.fare,
                }
    raise HTTPException(status_code=404, detail="no direct route found between these stops")


@app.put("/routes/{route_id}/fare")
def change_fare(route_id: int, data: FareUpdate):
    with Session(engine) as session:
        route = session.get(Route, route_id)
        if route is None:
            raise HTTPException(status_code=404, detail="route not found")
        route.fare = data.fare
        session.add(route)
        session.commit()
        session.refresh(route)
        return route_out(route)
