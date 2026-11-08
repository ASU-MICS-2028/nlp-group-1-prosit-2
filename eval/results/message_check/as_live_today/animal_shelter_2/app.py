from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///./pets.db", connect_args={"check_same_thread": False})


class Pet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    kind: str
    colour: str = ""
    adopted: bool = False


class PetCreate(BaseModel):
    name: str
    kind: str
    colour: str

    @field_validator("name", "kind", "colour")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class PetRead(BaseModel):
    id: int
    name: str
    kind: str
    colour: str
    adopted: bool


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(pet)")]
        if "colour" not in cols:
            conn.exec_driver_sql("ALTER TABLE pet ADD COLUMN colour VARCHAR NOT NULL DEFAULT ''")
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/pets", response_model=PetRead, status_code=201)
def add_pet(data: PetCreate):
    with Session(engine) as session:
        pet = Pet(name=data.name, kind=data.kind, colour=data.colour, adopted=False)
        session.add(pet)
        session.commit()
        session.refresh(pet)
        return PetRead(**pet.model_dump())


@app.get("/pets", response_model=List[PetRead])
def list_pets():
    with Session(engine) as session:
        pets = session.exec(select(Pet).order_by(Pet.id)).all()
        return [PetRead(**p.model_dump()) for p in pets]


@app.patch("/pets/{id}/adopted", response_model=PetRead)
def mark_adopted(id: int):
    with Session(engine) as session:
        pet = session.get(Pet, id)
        if pet is None:
            raise HTTPException(status_code=404, detail="No pet has that id")
        if pet.adopted:
            raise HTTPException(status_code=409, detail="This pet is already adopted")
        pet.adopted = True
        session.add(pet)
        session.commit()
        session.refresh(pet)
        return PetRead(**pet.model_dump())
