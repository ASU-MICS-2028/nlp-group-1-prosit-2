from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, or_, select

engine = create_engine("sqlite:///league.db", connect_args={"check_same_thread": False})


class Team(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class Fixture(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: date
    home_team_id: int = Field(foreign_key="team.id")
    away_team_id: int = Field(foreign_key="team.id")
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None


class TeamIn(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("A team must have a name")
        return v


class FixtureIn(BaseModel):
    date: date
    home_team_id: int
    away_team_id: int


class ScoreIn(BaseModel):
    home_goals: int = PField(ge=0)
    away_goals: int = PField(ge=0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Kumasi Community League Fixtures", lifespan=lifespan)


@app.post("/teams", status_code=201, response_model=Team)
def add_team(data: TeamIn):
    with Session(engine) as s:
        team = Team(name=data.name)
        s.add(team)
        s.commit()
        s.refresh(team)
        return team


@app.get("/teams", response_model=List[Team])
def list_teams():
    with Session(engine) as s:
        return s.exec(select(Team).order_by(Team.id)).all()


@app.post("/fixtures", status_code=201, response_model=Fixture)
def add_fixture(data: FixtureIn):
    if data.home_team_id == data.away_team_id:
        raise HTTPException(400, "A team cannot play against itself")
    with Session(engine) as s:
        if s.get(Team, data.home_team_id) is None:
            raise HTTPException(404, "Home team not found")
        if s.get(Team, data.away_team_id) is None:
            raise HTTPException(404, "Away team not found")
        fixture = Fixture(date=data.date, home_team_id=data.home_team_id,
                          away_team_id=data.away_team_id)
        s.add(fixture)
        s.commit()
        s.refresh(fixture)
        return fixture


@app.put("/fixtures/{fixture_id}/score", response_model=Fixture)
def record_score(fixture_id: int, data: ScoreIn):
    with Session(engine) as s:
        fixture = s.get(Fixture, fixture_id)
        if fixture is None:
            raise HTTPException(404, "Fixture not found")
        fixture.home_goals = data.home_goals
        fixture.away_goals = data.away_goals
        s.add(fixture)
        s.commit()
        s.refresh(fixture)
        return fixture


@app.get("/teams/{team_id}/fixtures", response_model=List[Fixture])
def team_fixtures(team_id: int):
    with Session(engine) as s:
        if s.get(Team, team_id) is None:
            raise HTTPException(404, "Team not found")
        return s.exec(
            select(Fixture)
            .where(or_(Fixture.home_team_id == team_id, Fixture.away_team_id == team_id))
            .order_by(Fixture.date, Fixture.id)
        ).all()
