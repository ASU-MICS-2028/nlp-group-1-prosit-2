# Second correct backend for football_fixtures: text ids, 200 on create, 422 for refusals, other paths and names.
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
teams, fixtures = {}, {}


class TeamIn(BaseModel):
    team_name: str


class FixtureIn(BaseModel):
    home: str
    away: str
    match_date: str


class ScoreIn(BaseModel):
    home_score: int
    away_score: int


@app.post("/teams")
def add_team(t: TeamIn):
    team = {"team_id": uuid.uuid4().hex, **t.model_dump()}
    teams[team["team_id"]] = team
    return team


@app.get("/teams")
def list_teams():
    return list(teams.values())


@app.post("/fixtures")
def create_fixture(f: FixtureIn):
    if f.home == f.away or f.home not in teams or f.away not in teams:
        raise HTTPException(422, "Need two different existing teams")
    fixture = {"fixture_id": uuid.uuid4().hex, **f.model_dump()}
    fixtures[fixture["fixture_id"]] = fixture
    return fixture


@app.get("/fixtures/{fixture_id}")
def get_fixture(fixture_id: str):
    if fixture_id not in fixtures:
        raise HTTPException(404, "No such fixture")
    return fixtures[fixture_id]


@app.post("/fixtures/{fixture_id}/score")
def record_score(fixture_id: str, s: ScoreIn):
    fixture = get_fixture(fixture_id)
    if s.home_score < 0 or s.away_score < 0:
        raise HTTPException(422, "Scores cannot be negative")
    fixture.update(s.model_dump())
    return fixture


@app.get("/teams/{team_id}/fixtures")
def team_fixtures(team_id: str):
    return [f for f in fixtures.values() if team_id in (f["home"], f["away"])]
