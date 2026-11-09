from datetime import date
from threading import Lock
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Kumasi Community Football League")

_lock = Lock()
teams: Dict[int, dict] = {}
fixtures: Dict[int, dict] = {}
_counters = {"team": 0, "fixture": 0}


class TeamIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class FixtureIn(BaseModel):
    date: date
    home_team_id: int
    away_team_id: int


class ScoreIn(BaseModel):
    home_goals: int = Field(..., ge=0)
    away_goals: int = Field(..., ge=0)


def _fixture_view(f: dict) -> dict:
    home = teams.get(f["home_team_id"])
    away = teams.get(f["away_team_id"])
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
    team = teams.get(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")
    return team


@app.get("/")
def root():
    return {"message": "Kumasi Community Football League API"}


@app.post("/teams", status_code=201)
def create_team(data: TeamIn):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Team name cannot be empty")
    with _lock:
        for t in teams.values():
            if t["name"].lower() == name.lower():
                raise HTTPException(status_code=409, detail="A team with this name already exists")
        _counters["team"] += 1
        team = {"id": _counters["team"], "name": name}
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
        f for f in fixtures.values()
        if f["home_team_id"] == team_id or f["away_team_id"] == team_id
    ]
    result.sort(key=lambda f: (f["date"], f["id"]))
    out = []
    for f in result:
        v = _fixture_view(f)
        v["venue"] = "home" if f["home_team_id"] == team_id else "away"
        out.append(v)
    return out


@app.post("/fixtures", status_code=201)
def create_fixture(data: FixtureIn):
    if data.home_team_id == data.away_team_id:
        raise HTTPException(status_code=400, detail="A team cannot play against itself")
    with _lock:
        _get_team(data.home_team_id)
        _get_team(data.away_team_id)
        _counters["fixture"] += 1
        f = {
            "id": _counters["fixture"],
            "date": data.date,
            "home_team_id": data.home_team_id,
            "away_team_id": data.away_team_id,
            "home_goals": None,
            "away_goals": None,
        }
        fixtures[f["id"]] = f
    return _fixture_view(f)


@app.get("/fixtures")
def list_fixtures():
    items = sorted(fixtures.values(), key=lambda f: (f["date"], f["id"]))
    return [_fixture_view(f) for f in items]


@app.get("/fixtures/{fixture_id}")
def get_fixture(fixture_id: int):
    f = fixtures.get(fixture_id)
    if f is None:
        raise HTTPException(status_code=404, detail=f"Fixture {fixture_id} not found")
    return _fixture_view(f)


def _record_score(fixture_id: int, data: ScoreIn):
    if data.home_goals < 0 or data.away_goals < 0:
        raise HTTPException(status_code=400, detail="Scores cannot be negative")
    with _lock:
        f = fixtures.get(fixture_id)
        if f is None:
            raise HTTPException(status_code=404, detail=f"Fixture {fixture_id} not found")
        f["home_goals"] = data.home_goals
        f["away_goals"] = data.away_goals
    return _fixture_view(f)


@app.put("/fixtures/{fixture_id}/score")
def put_score(fixture_id: int, data: ScoreIn):
    return _record_score(fixture_id, data)


@app.post("/fixtures/{fixture_id}/score")
def post_score(fixture_id: int, data: ScoreIn):
    return _record_score(fixture_id, data)
