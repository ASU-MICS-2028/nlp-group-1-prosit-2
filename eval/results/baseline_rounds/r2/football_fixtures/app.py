from datetime import date as Date
from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Kumasi Community Football League")

_lock = Lock()
_teams: Dict[int, dict] = {}
_fixtures: Dict[int, dict] = {}
_next_team_id = 1
_next_fixture_id = 1


class TeamIn(BaseModel):
    name: str


class FixtureIn(BaseModel):
    date: Date
    home_team_id: int
    away_team_id: int


class ScoreIn(BaseModel):
    home_goals: int = Field(..., ge=0)
    away_goals: int = Field(..., ge=0)


def _fixture_view(f: dict) -> dict:
    home = _teams.get(f["home_team_id"])
    away = _teams.get(f["away_team_id"])
    return {
        "id": f["id"],
        "date": f["date"].isoformat(),
        "home_team_id": f["home_team_id"],
        "home_team_name": home["name"] if home else None,
        "away_team_id": f["away_team_id"],
        "away_team_name": away["name"] if away else None,
        "home_goals": f["home_goals"],
        "away_goals": f["away_goals"],
        "played": f["home_goals"] is not None,
    }


def _get_team(team_id: int) -> dict:
    team = _teams.get(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")
    return team


def _get_fixture(fixture_id: int) -> dict:
    f = _fixtures.get(fixture_id)
    if f is None:
        raise HTTPException(status_code=404, detail=f"Fixture {fixture_id} not found")
    return f


@app.get("/")
def root():
    return {"message": "Kumasi Community Football League API"}


@app.post("/teams", status_code=201)
def create_team(data: TeamIn):
    global _next_team_id
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Team name cannot be empty")
    with _lock:
        for t in _teams.values():
            if t["name"].lower() == name.lower():
                raise HTTPException(status_code=409, detail="A team with this name already exists")
        team = {"id": _next_team_id, "name": name}
        _teams[_next_team_id] = team
        _next_team_id += 1
    return team


@app.get("/teams")
def list_teams():
    return list(_teams.values())


@app.get("/teams/{team_id}")
def get_team(team_id: int):
    return _get_team(team_id)


@app.get("/teams/{team_id}/fixtures")
def team_fixtures(team_id: int):
    _get_team(team_id)
    result = [
        _fixture_view(f)
        for f in _fixtures.values()
        if f["home_team_id"] == team_id or f["away_team_id"] == team_id
    ]
    result.sort(key=lambda x: (x["date"], x["id"]))
    for r in result:
        r["venue"] = "home" if r["home_team_id"] == team_id else "away"
    return result


@app.post("/fixtures", status_code=201)
def create_fixture(data: FixtureIn):
    global _next_fixture_id
    if data.home_team_id == data.away_team_id:
        raise HTTPException(status_code=400, detail="A team cannot play against itself")
    with _lock:
        _get_team(data.home_team_id)
        _get_team(data.away_team_id)
        f = {
            "id": _next_fixture_id,
            "date": data.date,
            "home_team_id": data.home_team_id,
            "away_team_id": data.away_team_id,
            "home_goals": None,
            "away_goals": None,
        }
        _fixtures[_next_fixture_id] = f
        _next_fixture_id += 1
    return _fixture_view(f)


@app.get("/fixtures")
def list_fixtures():
    result = [_fixture_view(f) for f in _fixtures.values()]
    result.sort(key=lambda x: (x["date"], x["id"]))
    return result


@app.get("/fixtures/{fixture_id}")
def get_fixture(fixture_id: int):
    return _fixture_view(_get_fixture(fixture_id))


def _record_score(fixture_id: int, data: ScoreIn):
    if data.home_goals < 0 or data.away_goals < 0:
        raise HTTPException(status_code=400, detail="A score can never be negative")
    with _lock:
        f = _get_fixture(fixture_id)
        f["home_goals"] = data.home_goals
        f["away_goals"] = data.away_goals
    return _fixture_view(f)


@app.post("/fixtures/{fixture_id}/score")
def record_score(fixture_id: int, data: ScoreIn):
    return _record_score(fixture_id, data)


@app.put("/fixtures/{fixture_id}/score")
def update_score(fixture_id: int, data: ScoreIn):
    return _record_score(fixture_id, data)
