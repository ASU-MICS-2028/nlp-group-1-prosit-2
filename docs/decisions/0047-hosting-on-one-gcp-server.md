# 0047. Host everything on one GCP server, each backend at its own path

- Status: Proposed
- Date: 2026-11-05
- Decided by: Joseph (GCP, default project settings); the rest to be signed off with the group

## Context

Lecture 8 and the instructor's answer: the agent must leave a backend running, hosted publicly, with its data, and return the link. Until now a build was tested and then stopped. Generated code is untrusted, so hosting must not loosen the sandbox (decision 0029).

## Options considered

- **One server running Docker, with Caddy in front.** One address and one HTTPS certificate. Each backend is a locked-down container at `/b/NAME`. About $30 a month, resizable.
- **A managed service per backend (such as Cloud Run).** No server to look after, but the SQLite file would need separate storage, and each backend would need its own deployment. More moving parts for one demo.
- **A separate subdomain per backend.** Nicer links, but a certificate for each one, on a shared free domain (`sslip.io`). We have no domain of our own.

## Decision

One `e2-medium` server (2 shared CPUs, 4 GB, 30 GB disk) in Belgium, in the existing GCP project on the default network. `runtime/deploy.py` runs each backend with the sandbox's own limits. It copies only `app.py` to `/srv/deployed/NAME/`, and Caddy serves it at `https://34-78-38-126.sslip.io/b/NAME`. SQLite stays the database (the instructor accepted it). Docker restarts everything after a reboot.

## Consequences

- A backend is reachable from anywhere, with `/docs` working, and keeps its data across restarts, redeploys and reboots (W4 rows 28–30).
- Backends cannot reach the internet, each other, the server's admin port or `.env` (row 29).
- The deployed folder is separate from the build folder, because the agent's checker deletes databases in the build folder.
- A crash of the whole server can lose the last few seconds of writes (row 30). There are no backups.
- One server is one point of failure, and many busy backends would share 4 GB.
- On Linux the sandbox now runs as the folder's owner, not user 1000, or the code could not write its database.
- Anyone can create data in a deployed backend: generated backends have no login unless the client asked for one. Safety of the public setup is still to do.
