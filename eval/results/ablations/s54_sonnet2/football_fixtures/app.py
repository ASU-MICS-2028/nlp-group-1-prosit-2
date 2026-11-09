from typing import Optional
from datetime import date as date_type
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as F, Session, create_engine, select, or_

engine = create_engine("sqlite:///app.db", connect_args={"check_same_thread": False})


class Team(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    name: str


class Fixture(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    date: date_type
    home_team_id: int
    away_team_id: int
    home_score: Optional[int] = None
    away_score: Optional[int] = None


class TeamIn(BaseModel):
    name: str = Field(min_length=1)


class FixtureIn(BaseModel):
    date: date_type
    home_team_id: int
    away_team_id: int


class ScoreIn(BaseModel):
    home_score: int = Field(ge=0)
    away_score: int = Field(ge=0)


SQLModel.metadata.create_all(engine)
app = FastAPI()


@app.post("/teams", status_code=201)
def create_team(t: TeamIn):
    with Session(engine) as s:
        team = Team(name=t.name)
        s.add(team)
        s.commit()
        s.refresh(team)
        return team


@app.get("/teams")
def list_teams():
    with Session(engine) as s:
        return s.exec(select(Team)).all()


@app.post("/fixtures", status_code=201)
def create_fixture(f: FixtureIn):
    if f.home_team_id == f.away_team_id:
        raise HTTPException(400, "A team cannot play against itself")
    with Session(engine) as s:
        if not s.get(Team, f.home_team_id) or not s.get(Team, f.away_team_id):
            raise HTTPException(404, "Team not found")
        fx = Fixture(**f.model_dump())
        s.add(fx)
        s.commit()
        s.refresh(fx)
        return fx


@app.get("/fixtures")
def list_fixtures():
    with Session(engine) as s:
        return s.exec(select(Fixture)).all()


@app.put("/fixtures/{fixture_id}/score")
def set_score(fixture_id: int, sc: ScoreIn):
    with Session(engine) as s:
        fx = s.get(Fixture, fixture_id)
        if not fx:
            raise HTTPException(404, "Fixture not found")
        fx.home_score = sc.home_score
        fx.away_score = sc.away_score
        s.add(fx)
        s.commit()
        s.refresh(fx)
        return fx


@app.get("/teams/{team_id}/fixtures")
def team_fixtures(team_id: int):
    with Session(engine) as s:
        if not s.get(Team, team_id):
            raise HTTPException(404, "Team not found")
        return s.exec(select(Fixture).where(
            or_(Fixture.home_team_id == team_id, Fixture.away_team_id == team_id))).all()
