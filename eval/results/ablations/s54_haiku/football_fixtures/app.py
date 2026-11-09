import datetime as dt
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, create_engine, select


class Team(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    name: str


class Fixture(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    home_team_id: int = SQLField(foreign_key="team.id")
    away_team_id: int = SQLField(foreign_key="team.id")
    date: dt.date
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None


class TeamIn(BaseModel):
    name: str = Field(min_length=1)


class FixtureIn(BaseModel):
    home_team_id: int
    away_team_id: int
    date: dt.date


class ScoreIn(BaseModel):
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)


engine = create_engine(
    "sqlite:///league.db",
    connect_args={"check_same_thread": False},
)
SQLModel.metadata.create_all(engine)

app = FastAPI(title="Community Football League")


def team_out(team: Team) -> dict:
    return {"id": team.id, "name": team.name}


def fixture_out(f: Fixture) -> dict:
    return {
        "id": f.id,
        "home_team_id": f.home_team_id,
        "away_team_id": f.away_team_id,
        "date": f.date.isoformat(),
        "home_goals": f.home_goals,
        "away_goals": f.away_goals,
    }


@app.post("/teams", status_code=201)
def create_team(body: TeamIn):
    with Session(engine) as session:
        team = Team(name=body.name)
        session.add(team)
        session.commit()
        session.refresh(team)
        return team_out(team)


@app.post("/fixtures", status_code=201)
def create_fixture(body: FixtureIn):
    if body.home_team_id == body.away_team_id:
        raise HTTPException(status_code=400, detail="A team cannot play against itself")
    with Session(engine) as session:
        for team_id in (body.home_team_id, body.away_team_id):
            if session.get(Team, team_id) is None:
                raise HTTPException(status_code=404, detail=f"Team {team_id} not found")
        fixture = Fixture(
            home_team_id=body.home_team_id,
            away_team_id=body.away_team_id,
            date=body.date,
        )
        session.add(fixture)
        session.commit()
        session.refresh(fixture)
        return fixture_out(fixture)


@app.post("/fixtures/{fixture_id}/score")
def record_score(fixture_id: int, body: ScoreIn):
    with Session(engine) as session:
        fixture = session.get(Fixture, fixture_id)
        if fixture is None:
            raise HTTPException(status_code=404, detail="Fixture not found")
        fixture.home_goals = body.home_goals
        fixture.away_goals = body.away_goals
        session.add(fixture)
        session.commit()
        session.refresh(fixture)
        return fixture_out(fixture)


@app.get("/teams/{team_id}/fixtures")
def team_fixtures(team_id: int):
    with Session(engine) as session:
        if session.get(Team, team_id) is None:
            raise HTTPException(status_code=404, detail="Team not found")
        statement = (
            select(Fixture)
            .where(
                (Fixture.home_team_id == team_id) | (Fixture.away_team_id == team_id)
            )
            .order_by(Fixture.date, Fixture.id)
        )
        return [fixture_out(f) for f in session.exec(statement).all()]
