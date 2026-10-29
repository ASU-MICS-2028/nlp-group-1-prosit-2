# MUTANT due_includes_collected: the due list no longer leaves out collected orders
# Reference backend for tailoring_orders: proves the hidden tests are right.
# Deliberately uses different names (full_name, sizes, item, ready_on, cost, paid, /clients, /jobs) to exercise ops.json.
from datetime import date
from itertools import count

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
clients, jobs = {}, {}
ids = count(1)


class Sizes(BaseModel):
    chest: float
    waist: float
    hip: float
    length: float


class ClientIn(BaseModel):
    full_name: str
    phone: str
    sizes: Sizes


class JobIn(BaseModel):
    item: str
    ready_on: date
    cost: float
    paid: float


def find(store, key):
    if key not in store:
        raise HTTPException(404, "Not found")
    return store[key]


@app.post("/clients", status_code=201)
def create_client(c: ClientIn):
    client = {"id": next(ids), **c.model_dump()}
    clients[client["id"]] = client
    return client


@app.get("/clients/{client_id}")
def get_client(client_id: int):
    return find(clients, client_id)


@app.post("/clients/{client_id}/jobs", status_code=201)
def create_job(client_id: int, j: JobIn):
    find(clients, client_id)
    if j.paid > j.cost:
        raise HTTPException(400, "Deposit cannot be more than the price")
    job = {"id": next(ids), "client_id": client_id, **j.model_dump(), "picked_up": False}
    jobs[job["id"]] = job
    return job


@app.get("/clients/{client_id}/jobs")
def list_client_jobs(client_id: int):
    find(clients, client_id)
    return [j for j in jobs.values() if j["client_id"] == client_id]


@app.get("/jobs/due")
def list_due(until: date):
    return [j for j in jobs.values() if j["ready_on"] <= until]


@app.get("/jobs/{job_id}")
def get_job(job_id: int):
    return find(jobs, job_id)


@app.post("/jobs/{job_id}/pickup")
def pick_up(job_id: int):
    job = find(jobs, job_id)
    job["picked_up"] = True
    return job
