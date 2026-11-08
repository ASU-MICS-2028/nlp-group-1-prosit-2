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
    colour: str
    adopted: bool = False


class PetCreate(BaseModel):
    name: str
    kind: str
    colour: str

    @field_validator("name", "kind", "colour")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if v is None or not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/pets", status_code=201, response_model=Pet)
def add_pet(data: PetCreate):
    with Session(engine) as s:
        pet = Pet(name=data.name, kind=data.kind, colour=data.colour, adopted=False)
        s.add(pet)
        s.commit()
        s.refresh(pet)
        return pet


@app.get("/pets", response_model=List[Pet])
def list_pets():
    with Session(engine) as s:
        return s.exec(select(Pet).order_by(Pet.id)).all()


@app.patch("/pets/{id}/adopted", response_model=Pet)
def mark_adopted(id: int):
    with Session(engine) as s:
        pet = s.get(Pet, id)
        if pet is None:
            raise HTTPException(status_code=404, detail="No pet has that id")
        if pet.adopted:
            raise HTTPException(status_code=409, detail="Pet is already adopted")
        pet.adopted = True
        s.add(pet)
        s.commit()
        s.refresh(pet)
        return pet
