from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///shelter.db", connect_args={"check_same_thread": False})


class Pet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    kind: str
    colour: str
    adopted: bool = False


class PetIn(BaseModel):
    name: Optional[str] = None
    kind: Optional[str] = None
    colour: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/pets", status_code=201, response_model=Pet)
def add_pet(data: PetIn):
    name = data.name.strip() if isinstance(data.name, str) else ""
    kind = data.kind.strip() if isinstance(data.kind, str) else ""
    if not name:
        raise HTTPException(status_code=422, detail="A pet must have a name.")
    if not kind:
        raise HTTPException(status_code=422, detail="A pet must have a kind.")
    colour = data.colour.strip() if isinstance(data.colour, str) else ""
    if not colour:
        raise HTTPException(status_code=422, detail="A pet must have a colour.")
    with Session(engine) as session:
        pet = Pet(name=name, kind=kind, colour=colour, adopted=False)
        session.add(pet)
        session.commit()
        session.refresh(pet)
        return pet


@app.get("/pets", response_model=List[Pet])
def list_pets():
    with Session(engine) as session:
        return session.exec(select(Pet).order_by(Pet.id)).all()


@app.patch("/pets/{id}/adopted", response_model=Pet)
def mark_adopted(id: int):
    with Session(engine) as session:
        pet = session.get(Pet, id)
        if pet is None:
            raise HTTPException(status_code=404, detail="No pet has that id.")
        if pet.adopted:
            raise HTTPException(status_code=409, detail="This pet is already adopted.")
        pet.adopted = True
        session.add(pet)
        session.commit()
        session.refresh(pet)
        return pet
