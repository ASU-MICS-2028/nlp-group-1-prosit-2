# MUTANT unknown_team_allowed: '    if m.host not in clubs:' instead of '    if m.host not in clubs or m.visitor not in clubs:'
# Reference backend for football_fixtures: proves the hidden tests are right.
# Deliberately uses different names (club, host, visitor, kickoff_date, host_score, visitor_score) to exercise ops.json translation.
from datetime import date

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()
clubs, matches = {}, {}


class ClubIn(BaseModel):
    club: str


class MatchIn(BaseModel):
    host: int
    visitor: int
    kickoff_date: date


class ResultIn(BaseModel):
    host_score: int = Field(ge=0)
    visitor_score: int = Field(ge=0)


def find_match(match_id):
    if match_id not in matches:
        raise HTTPException(404, "No such fixture")
    return matches[match_id]


@app.post("/league/clubs", status_code=201)
def add_team(c: ClubIn):
    club = {"id": len(clubs) + 1, **c.model_dump()}
    clubs[club["id"]] = club
    return club


@app.get("/league/clubs")
def list_teams():
    return list(clubs.values())


@app.post("/league/matches", status_code=201)
def create_fixture(m: MatchIn):
    if m.host not in clubs:
        raise HTTPException(400, "Unknown team")
    if m.host == m.visitor:
        raise HTTPException(400, "A team cannot play itself")
    match = {"id": len(matches) + 1, **m.model_dump(), "host_score": None, "visitor_score": None}
    matches[match["id"]] = match
    return match


@app.get("/league/matches/{match_id}")
def get_fixture(match_id: int):
    return find_match(match_id)


@app.put("/league/matches/{match_id}/result")
def record_score(match_id: int, r: ResultIn):
    match = find_match(match_id)
    match["host_score"] = r.host_score
    match["visitor_score"] = r.visitor_score
    return match


@app.get("/league/clubs/{club_id}/matches")
def team_fixtures(club_id: int):
    if club_id not in clubs:
        raise HTTPException(404, "No such team")
    return [m for m in matches.values() if club_id in (m["host"], m["visitor"])]
