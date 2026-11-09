from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Field as F, SQLModel, Session, create_engine, select, or_


class Team(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    name: str


class Fixture(SQLModel, table=True):
    id: Optional[int] = F(default=None, primary_key=True)
    date: date
    home_team_id: int
    away_team_id: int
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None


class TeamIn(BaseModel):
    name: str = Field(min_length=1)


class FixtureIn(BaseModel):
    date: date
    home_team_id: int
    away_team_id: int


class ScoreIn(BaseModel):
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)


engine = create_engine("sqlite:///app.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)

app = FastAPI()


@app.post("/teams", status_code=201)
def create_team(body: TeamIn):
    if not body.name.strip():
        raise HTTPException(422, "name required")
    with Session(engine) as s:
        t = Team(name=body.name)
        s.add(t)
        s.commit()
        s.refresh(t)
        return t


@app.get("/teams")
def list_teams():
    with Session(engine) as s:
        return s.exec(select(Team)).all()


@app.post("/fixtures", status_code=201)
def create_fixture(body: FixtureIn):
    if body.home_team_id == body.away_team_id:
        raise HTTPException(400, "A team cannot play against itself")
    with Session(engine) as s:
        if not s.get(Team, body.home_team_id) or not s.get(Team, body.away_team_id):
            raise HTTPException(404, "Team not found")
        f = Fixture(**body.model_dump())
        s.add(f)
        s.commit()
        s.refresh(f)
        return f


@app.get("/fixtures/{fixture_id}")
def get_fixture(fixture_id: int):
    with Session(engine) as s:
        f = s.get(Fixture, fixture_id)
        if not f:
            raise HTTPException(404, "Fixture not found")
        return f


@app.put("/fixtures/{fixture_id}/score")
def set_score(fixture_id: int, body: ScoreIn):
    with Session(engine) as s:
        f = s.get(Fixture, fixture_id)
        if not f:
            raise HTTPException(404, "Fixture not found")
        f.home_goals = body.home_goals
        f.away_goals = body.away_goals
        s.add(f)
        s.commit()
        s.refresh(f)
        return f


@app.get("/teams/{team_id}/fixtures")
def team_fixtures(team_id: int):
    with Session(engine) as s:
        if not s.get(Team, team_id):
            raise HTTPException(404, "Team not found")
        return s.exec(
            select(Fixture).where(
                or_(Fixture.home_team_id == team_id, Fixture.away_team_id == team_id)
            )
        ).all()
