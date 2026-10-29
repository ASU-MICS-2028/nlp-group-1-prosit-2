# Records that belong to another record (one-to-many)

Use when: one thing has many others: a class has many pupils, a shop has many products, a person has many visits.
Give the child table a `foreign_key` column pointing at the parent's id, create children under the parent's path
(POST /parents/{id}/children), answer 404 when the parent does not exist, and list only that parent's children.

```python
from fastapi import FastAPI, HTTPException
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


class PlayerIn(SQLModel):
    name: str


class Player(PlayerIn, table=True):
    id: int | None = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="team.id", index=True)


SQLModel.metadata.create_all(engine)
app = FastAPI()


@app.post("/teams", status_code=201)
def add_team(t: Team) -> Team:
    with Session(engine) as s:
        s.add(t)
        s.commit()
        s.refresh(t)
        return t


@app.post("/teams/{team_id}/players", status_code=201)
def add_player(team_id: int, p: PlayerIn) -> Player:
    with Session(engine) as s:
        if s.get(Team, team_id) is None:
            raise HTTPException(404, "No such team")
        row = Player(**p.model_dump(), team_id=team_id)
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


@app.get("/teams/{team_id}/players")
def players(team_id: int) -> list[Player]:
    with Session(engine) as s:
        if s.get(Team, team_id) is None:
            raise HTTPException(404, "No such team")
        return s.exec(select(Player).where(Player.team_id == team_id)).all()
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
a, b = c.post("/teams", json={"name": "A"}).json(), c.post("/teams", json={"name": "B"}).json()
c.post(f"/teams/{a['id']}/players", json={"name": "Kwesi"})
assert [p["name"] for p in c.get(f"/teams/{a['id']}/players").json()] == ["Kwesi"]
assert c.get(f"/teams/{b['id']}/players").json() == []
assert c.post("/teams/99/players", json={"name": "X"}).status_code == 404
```
