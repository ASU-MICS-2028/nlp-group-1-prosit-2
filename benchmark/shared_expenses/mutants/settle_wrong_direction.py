# MUTANT settle_wrong_direction: '    net[p.sender] -= pesewas\n    net[p.receiver] += pesewas\n' instead of '    net[p.sender] += pesewas\n    net[p.receiver] -= pesewas\n'
# Reference backend for shared_expenses: proves the hidden tests are right.
# Deliberately uses different names (title, payer, cedis, among, who, net, /circles) to exercise ops.json.
# Money is kept in whole pesewas so splits add up exactly.
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()
circles, people, net = {}, {}, {}  # net: person id -> balance in pesewas


class CircleIn(BaseModel):
    title: str


class PersonIn(BaseModel):
    name: str


class ExpenseIn(BaseModel):
    payer: int
    cedis: Decimal = Field(gt=0, decimal_places=2)
    among: list[int] = Field(min_length=1)


class PaymentIn(BaseModel):
    sender: int
    receiver: int
    cedis: Decimal = Field(gt=0, decimal_places=2)


def find_circle(cid):
    if cid not in circles:
        raise HTTPException(404, "No such group")


def check_member(cid, pid):
    if pid not in people or people[pid]["circle"] != cid:
        raise HTTPException(400, f"{pid} is not a member of this group")


@app.post("/circles", status_code=201)
def create_circle(c: CircleIn):
    circle = {"id": len(circles) + 1, **c.model_dump()}
    circles[circle["id"]] = circle
    return circle


@app.post("/circles/{cid}/people", status_code=201)
def add_person(cid: int, p: PersonIn):
    find_circle(cid)
    person = {"id": len(people) + 1, "circle": cid, **p.model_dump()}
    people[person["id"]] = person
    net[person["id"]] = 0
    return person


@app.post("/circles/{cid}/spending", status_code=201)
def add_expense(cid: int, e: ExpenseIn):
    find_circle(cid)
    check_member(cid, e.payer)
    for pid in e.among:
        check_member(cid, pid)
    pesewas = int(e.cedis * 100)
    share, extra = divmod(pesewas, len(e.among))
    net[e.payer] += pesewas
    for i, pid in enumerate(e.among):
        net[pid] -= share + (1 if i < extra else 0)
    return {"payer": e.payer, "cedis": float(e.cedis), "among": e.among}


@app.post("/circles/{cid}/paybacks", status_code=201)
def pay_back(cid: int, p: PaymentIn):
    find_circle(cid)
    check_member(cid, p.sender)
    check_member(cid, p.receiver)
    if p.sender == p.receiver:
        raise HTTPException(400, "Nobody can pay themselves back")
    pesewas = int(p.cedis * 100)
    net[p.sender] -= pesewas
    net[p.receiver] += pesewas
    return {"sender": p.sender, "receiver": p.receiver, "cedis": float(p.cedis)}


@app.get("/circles/{cid}/net")
def balances(cid: int):
    find_circle(cid)
    return [{"who": pid, "name": p["name"], "net": net[pid] / 100} for pid, p in people.items() if p["circle"] == cid]
