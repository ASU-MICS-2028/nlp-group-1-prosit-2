from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field as PField
from sqlmodel import Field, Session, SQLModel, create_engine, select, or_

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
    name: str = PField(min_length=1)


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


app = FastAPI(title="Kumasi Community Football League", lifespan=lifespan)


@app.post("/teams", status_code=201)
def add_team(data: TeamIn):
    with Session(engine) as s:
        team = Team(name=data.name)
        s.add(team)
        s.commit()
        s.refresh(team)
        return team


@app.get("/teams")
def list_teams():
    with Session(engine) as s:
        return s.exec(select(Team)).all()


@app.post("/fixtures", status_code=201)
def schedule_fixture(data: FixtureIn):
    if data.home_team_id == data.away_team_id:
        raise HTTPException(400, "A team cannot play against itself")
    with Session(engine) as s:
        for tid in (data.home_team_id, data.away_team_id):
            if not s.get(Team, tid):
                raise HTTPException(404, f"Team {tid} not found")
        fx = Fixture(date=data.date, home_team_id=data.home_team_id, away_team_id=data.away_team_id)
        s.add(fx)
        s.commit()
        s.refresh(fx)
        return fx


@app.put("/fixtures/{fixture_id}/score")
def record_score(fixture_id: int, data: ScoreIn):
    with Session(engine) as s:
        fx = s.get(Fixture, fixture_id)
        if not fx:
            raise HTTPException(404, "Fixture not found")
        fx.home_goals = data.home_goals
        fx.away_goals = data.away_goals
        s.add(fx)
        s.commit()
        s.refresh(fx)
        return fx


@app.get("/teams/{team_id}/fixtures")
def team_fixtures(team_id: int):
    with Session(engine) as s:
        if not s.get(Team, team_id):
            raise HTTPException(404, "Team not found")
        return s.exec(
            select(Fixture)
            .where(or_(Fixture.home_team_id == team_id, Fixture.away_team_id == team_id))
            .order_by(Fixture.date)
        ).all()
