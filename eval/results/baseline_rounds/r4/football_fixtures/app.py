from datetime import date
from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Kumasi Community Football League")

_lock = Lock()
teams: Dict[int, dict] = {}
fixtures: Dict[int, dict] = {}
_counters = {"team": 0, "fixture": 0}


class TeamIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Team name cannot be empty")
        return v


class FixtureIn(BaseModel):
    date: date
    home_team_id: int
    away_team_id: int


class ScoreIn(BaseModel):
    home_goals: int = Field(..., ge=0)
    away_goals: int = Field(..., ge=0)


def _get_team(team_id: int) -> dict:
    team = teams.get(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")
    return team


def _get_fixture(fixture_id: int) -> dict:
    fx = fixtures.get(fixture_id)
    if fx is None:
        raise HTTPException(status_code=404, detail=f"Fixture {fixture_id} not found")
    return fx


def _fixture_out(fx: dict) -> dict:
    home = teams.get(fx["home_team_id"], {})
    away = teams.get(fx["away_team_id"], {})
    return {
        "id": fx["id"],
        "date": fx["date"].isoformat(),
        "home_team_id": fx["home_team_id"],
        "home_team_name": home.get("name"),
        "away_team_id": fx["away_team_id"],
        "away_team_name": away.get("name"),
        "home_goals": fx["home_goals"],
        "away_goals": fx["away_goals"],
        "played": fx["home_goals"] is not None,
    }


@app.get("/")
def root():
    return {"message": "Kumasi Community Football League API"}


@app.post("/teams", status_code=201)
def create_team(payload: TeamIn):
    with _lock:
        for t in teams.values():
            if t["name"].lower() == payload.name.lower():
                raise HTTPException(status_code=409, detail="A team with this name already exists")
        _counters["team"] += 1
        team = {"id": _counters["team"], "name": payload.name}
        teams[team["id"]] = team
        return team


@app.get("/teams")
def list_teams():
    return list(teams.values())


@app.get("/teams/{team_id}")
def get_team(team_id: int):
    return _get_team(team_id)


@app.get("/teams/{team_id}/fixtures")
def team_fixtures(team_id: int):
    _get_team(team_id)
    result = [
        _fixture_out(fx)
        for fx in fixtures.values()
        if fx["home_team_id"] == team_id or fx["away_team_id"] == team_id
    ]
    result.sort(key=lambda f: (f["date"], f["id"]))
    return result


@app.post("/fixtures", status_code=201)
def create_fixture(payload: FixtureIn):
    with _lock:
        if payload.home_team_id == payload.away_team_id:
            raise HTTPException(status_code=400, detail="A team cannot play against itself")
        _get_team(payload.home_team_id)
        _get_team(payload.away_team_id)
        _counters["fixture"] += 1
        fx = {
            "id": _counters["fixture"],
            "date": payload.date,
            "home_team_id": payload.home_team_id,
            "away_team_id": payload.away_team_id,
            "home_goals": None,
            "away_goals": None,
        }
        fixtures[fx["id"]] = fx
        return _fixture_out(fx)


@app.get("/fixtures")
def list_fixtures():
    result = [_fixture_out(fx) for fx in fixtures.values()]
    result.sort(key=lambda f: (f["date"], f["id"]))
    return result


@app.get("/fixtures/{fixture_id}")
def get_fixture(fixture_id: int):
    return _fixture_out(_get_fixture(fixture_id))


def _record_score(fixture_id: int, payload: ScoreIn) -> dict:
    with _lock:
        fx = _get_fixture(fixture_id)
        if payload.home_goals < 0 or payload.away_goals < 0:
            raise HTTPException(status_code=422, detail="A score can never be negative")
        fx["home_goals"] = payload.home_goals
        fx["away_goals"] = payload.away_goals
        return _fixture_out(fx)


@app.put("/fixtures/{fixture_id}/score")
def put_score(fixture_id: int, payload: ScoreIn):
    return _record_score(fixture_id, payload)


@app.post("/fixtures/{fixture_id}/score")
def post_score(fixture_id: int, payload: ScoreIn):
    return _record_score(fixture_id, payload)


@app.patch("/fixtures/{fixture_id}/score")
def patch_score(fixture_id: int, payload: ScoreIn):
    return _record_score(fixture_id, payload)
