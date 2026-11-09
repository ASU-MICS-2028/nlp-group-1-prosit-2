from datetime import date as date_type
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select, or_

engine = create_engine("sqlite:///league.db", connect_args={"check_same_thread": False})


class Team(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class Fixture(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: date_type
    home_team_id: int
    away_team_id: int
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None


SQLModel.metadata.create_all(engine)
app = FastAPI()


class TeamIn(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def nonempty(cls, v):
        if not v.strip():
            raise ValueError("name must not be empty")
        return v


class FixtureIn(BaseModel):
    date: date_type
    home_team_id: int
    away_team_id: int


class ScoreIn(BaseModel):
    home_goals: int
    away_goals: int

    @field_validator("home_goals", "away_goals")
    @classmethod
    def nonneg(cls, v):
        if v < 0:
            raise ValueError("score cannot be negative")
        return v


def fx(f):
    return {
        "id": f.id,
        "date": f.date.isoformat(),
        "home_team_id": f.home_team_id,
        "away_team_id": f.away_team_id,
        "home_goals": f.home_goals,
        "away_goals": f.away_goals,
    }


@app.post("/teams", status_code=201)
def create_team(body: TeamIn):
    with Session(engine) as s:
        t = Team(name=body.name)
        s.add(t)
        s.commit()
        s.refresh(t)
        return {"id": t.id, "name": t.name}


@app.get("/teams")
def list_teams():
    with Session(engine) as s:
        return [{"id": t.id, "name": t.name} for t in s.exec(select(Team)).all()]


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
        return fx(f)


@app.get("/fixtures")
def list_fixtures():
    with Session(engine) as s:
        return [fx(f) for f in s.exec(select(Fixture).order_by(Fixture.date, Fixture.id)).all()]


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
        return fx(f)


@app.get("/teams/{team_id}/fixtures")
def team_fixtures(team_id: int):
    with Session(engine) as s:
        if not s.get(Team, team_id):
            raise HTTPException(404, "Team not found")
        q = (
            select(Fixture)
            .where(or_(Fixture.home_team_id == team_id, Fixture.away_team_id == team_id))
            .order_by(Fixture.date, Fixture.id)
        )
        return [fx(f) for f in s.exec(q).all()]
