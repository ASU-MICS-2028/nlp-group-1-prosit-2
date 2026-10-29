# Totals, averages and sorted lists (scores, rankings, summaries)

Use when: the client wants a computed figure (an average mark, a total, a weighted score) or a list in a given order
(highest first, alphabetical, newest first). Compute from the saved rows when asked, rather than storing the result;
round only for display; return a clear value (not an error) when there is nothing to average.

```python
from fastapi import FastAPI
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Score(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    player: str = Field(index=True)
    points: float = Field(ge=0)
    weight: int = Field(default=1, gt=0)


SQLModel.metadata.create_all(engine)
app = FastAPI()


@app.post("/scores", status_code=201)
def add(sc: Score) -> Score:
    with Session(engine) as s:
        s.add(sc)
        s.commit()
        s.refresh(sc)
        return sc


@app.get("/players/{player}/average")
def average(player: str) -> dict:
    with Session(engine) as s:
        rows = s.exec(select(Score).where(Score.player == player)).all()
    total_weight = sum(r.weight for r in rows)
    avg = sum(r.points * r.weight for r in rows) / total_weight if total_weight else None  # weighted mean
    return {"player": player, "average": None if avg is None else round(avg, 2)}


@app.get("/leaderboard")
def leaderboard() -> list[dict]:
    with Session(engine) as s:
        rows = s.exec(select(Score)).all()
    totals: dict[str, float] = {}
    for r in rows:
        totals[r.player] = totals.get(r.player, 0) + r.points
    return [{"player": p, "total": t} for p, t in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))]
```

```python check
from fastapi.testclient import TestClient
c = TestClient(app)
c.post("/scores", json={"player": "Abena", "points": 4, "weight": 3})
c.post("/scores", json={"player": "Abena", "points": 3, "weight": 1})
c.post("/scores", json={"player": "Yaw", "points": 9})
assert c.get("/players/Abena/average").json()["average"] == 3.75
assert c.get("/players/Nobody/average").json()["average"] is None
assert [r["player"] for r in c.get("/leaderboard").json()] == ["Yaw", "Abena"]
```
