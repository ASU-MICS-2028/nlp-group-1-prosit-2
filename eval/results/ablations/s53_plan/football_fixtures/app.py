from contextlib import asynccontextmanager
from datetime import date as Date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictInt, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, or_

engine = create_engine("sqlite:///league.db", connect_args={"check_same_thread": False})


class Team(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class Fixture(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: Date
    home_team_id: int = Field(foreign_key="team.id")
    away_team_id: int = Field(foreign_key="team.id")
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None


class TeamIn(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("A team must have a name.")
        return v


class FixtureIn(BaseModel):
    date: Date
    home_team_id: StrictInt
    away_team_id: StrictInt


class ScoreIn(BaseModel):
    home_goals: StrictInt
    away_goals: StrictInt

    @field_validator("home_goals", "away_goals")
    @classmethod
    def not_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Goals can never be negative.")
        return v


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Kumasi Community Football League", lifespan=lifespan)


@app.post("/teams", status_code=201, response_model=Team)
def add_team(data: TeamIn):
    with Session(engine) as s:
        team = Team(name=data.name)
        s.add(team)
        s.commit()
        s.refresh(team)
        return team


@app.get("/teams", response_model=list[Team])
def list_teams():
    with Session(engine) as s:
        return s.exec(select(Team).order_by(Team.id)).all()


@app.post("/fixtures", status_code=201, response_model=Fixture)
def add_fixture(data: FixtureIn):
    if data.home_team_id == data.away_team_id:
        raise HTTPException(422, "A team cannot play against itself.")
    with Session(engine) as s:
        if not s.get(Team, data.home_team_id):
            raise HTTPException(404, "Home team not found.")
        if not s.get(Team, data.away_team_id):
            raise HTTPException(404, "Away team not found.")
        fx = Fixture(date=data.date, home_team_id=data.home_team_id, away_team_id=data.away_team_id)
        s.add(fx)
        s.commit()
        s.refresh(fx)
        return fx


@app.put("/fixtures/{fixtureNumber}/score", response_model=Fixture)
def record_score(fixtureNumber: int, data: ScoreIn):
    with Session(engine) as s:
        fx = s.get(Fixture, fixtureNumber)
        if not fx:
            raise HTTPException(404, "Fixture not found.")
        fx.home_goals = data.home_goals
        fx.away_goals = data.away_goals
        s.add(fx)
        s.commit()
        s.refresh(fx)
        return fx


@app.get("/teams/{teamNumber}/fixtures", response_model=list[Fixture])
def team_fixtures(teamNumber: int):
    with Session(engine) as s:
        if not s.get(Team, teamNumber):
            raise HTTPException(404, "Team not found.")
        q = select(Fixture).where(
            or_(Fixture.home_team_id == teamNumber, Fixture.away_team_id == teamNumber)
        ).order_by(Fixture.date, Fixture.id)
        return s.exec(q).all()
