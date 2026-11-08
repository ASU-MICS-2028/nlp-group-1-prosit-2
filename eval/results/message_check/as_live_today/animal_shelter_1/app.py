from contextlib import asynccontextmanager
from typing import Optional, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Session, create_engine, select

engine = create_engine("sqlite:///pets.db", connect_args={"check_same_thread": False})


class Pet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    kind: str
    colour: str = ""
    adopted: bool = False


class PetIn(BaseModel):
    name: Any = None
    kind: Any = None
    colour: Any = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    # Add the colour column to an older database file that lacks it.
    with engine.begin() as conn:
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(pet)")]
        if "colour" not in cols:
            conn.exec_driver_sql("ALTER TABLE pet ADD COLUMN colour VARCHAR NOT NULL DEFAULT ''")
    yield


app = FastAPI(lifespan=lifespan)


def _clean(value, field):
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail=f"A pet must have a {field}.")
    return value.strip()


@app.post("/pets", status_code=201)
def add_pet(data: PetIn):
    name = _clean(data.name, "name")
    kind = _clean(data.kind, "kind")
    colour = _clean(data.colour, "colour")
    with Session(engine) as s:
        pet = Pet(name=name, kind=kind, colour=colour, adopted=False)
        s.add(pet)
        s.commit()
        s.refresh(pet)
        return pet.model_dump()


@app.get("/pets")
def list_pets():
    with Session(engine) as s:
        return [p.model_dump() for p in s.exec(select(Pet).order_by(Pet.id)).all()]


@app.patch("/pets/{id}/adopted")
def mark_adopted(id: int):
    with Session(engine) as s:
        pet = s.get(Pet, id)
        if pet is None:
            raise HTTPException(status_code=404, detail="No pet has that id number.")
        if pet.adopted:
            raise HTTPException(status_code=409, detail="That pet is already marked as adopted.")
        pet.adopted = True
        s.add(pet)
        s.commit()
        s.refresh(pet)
        return pet.model_dump()
