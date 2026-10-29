# Reference backend for susu_ledger: proves the hidden tests are right.
# Deliberately uses different names (label, full_name, member, round_no, cedis, /susu-groups) to exercise ops.json.
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()
groups, members, dues, collections = {}, {}, [], []


class GroupIn(BaseModel):
    label: str


class MemberIn(BaseModel):
    full_name: str
    phone: str


class DueIn(BaseModel):
    member: int
    round_no: int = Field(ge=1)
    cedis: Decimal = Field(gt=0, decimal_places=2)


class CollectIn(BaseModel):
    member: int
    round_no: int = Field(ge=1)


def find_group(gid):
    if gid not in groups:
        raise HTTPException(404, "No such group")
    return groups[gid]


def find_member(gid, mid):
    find_group(gid)
    if mid not in members or members[mid]["group"] != gid:
        raise HTTPException(404, "No such member in this group")
    return members[mid]


def show(row):
    return {**row, "cedis": float(row["cedis"])}


@app.post("/susu-groups", status_code=201)
def create_group(g: GroupIn):
    group = {"id": len(groups) + 1, **g.model_dump()}
    groups[group["id"]] = group
    return group


@app.post("/susu-groups/{gid}/people", status_code=201)
def add_member(gid: int, m: MemberIn):
    find_group(gid)
    member = {"id": len(members) + 1, "group": gid, **m.model_dump()}
    members[member["id"]] = member
    return member


@app.get("/susu-groups/{gid}/people")
def list_members(gid: int):
    find_group(gid)
    return [m for m in members.values() if m["group"] == gid]


@app.post("/susu-groups/{gid}/dues", status_code=201)
def record_due(gid: int, d: DueIn):
    find_member(gid, d.member)
    if any(c["group"] == gid and c["round_no"] == d.round_no for c in collections):
        raise HTTPException(409, "That round has already been collected")
    due = {"id": len(dues) + 1, "group": gid, **d.model_dump()}
    dues.append(due)
    return show(due)


@app.post("/susu-groups/{gid}/collections", status_code=201)
def collect(gid: int, c: CollectIn):
    find_member(gid, c.member)
    done = [x for x in collections if x["group"] == gid]
    if any(x["round_no"] == c.round_no for x in done):
        raise HTTPException(409, "That round has already been collected")
    if any(x["member"] == c.member for x in done):
        raise HTTPException(409, "This member has already collected")
    pot = sum((d["cedis"] for d in dues if d["group"] == gid and d["round_no"] == c.round_no), Decimal(0))
    if pot == 0:
        raise HTTPException(400, "Nothing has been paid into that round")
    row = {"id": len(collections) + 1, "group": gid, "member": c.member, "round_no": c.round_no, "cedis": pot}
    collections.append(row)
    return show(row)


@app.get("/susu-groups/{gid}/collections")
def list_collections(gid: int):
    find_group(gid)
    return [show(x) for x in collections if x["group"] == gid]


@app.get("/susu-groups/{gid}/people/{mid}/statement")
def statement(gid: int, mid: int):
    m = find_member(gid, mid)
    paid = sum((d["cedis"] for d in dues if d["member"] == mid), Decimal(0))
    got = sum((x["cedis"] for x in collections if x["member"] == mid), Decimal(0))
    return {"member": mid, "full_name": m["full_name"], "paid_in": float(paid), "collected": float(got)}
