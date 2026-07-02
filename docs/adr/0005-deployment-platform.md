# ADR 0005 — Deployment platform: Railway, one image, semver-pinned CD

- **Status:** Accepted
- **Milestone:** M5 (ship — the platform deploy half; the case study is separate)
- **Extends:** [ADR 0003](0003-observability.md) (the `/readyz` probe becomes the
  deploy gate) and [ADR 0004](0004-realtime-websockets.md) (daphne serves HTTP +
  WebSockets from one process, so one public service suffices).

## Context

M1–M4 produced a production-hardened image on GHCR (`ghcr.io/edjchapman/foreman`,
`:latest` + semver per release, publicly pullable, SLSA-attested) and env-driven
settings — but nothing ran it publicly. The demo needs three always-on processes
from that one image (web/daphne, Celery worker, Celery beat), managed Postgres 16
and Redis, WebSocket support end-to-end, a release step for `migrate`, and a
portfolio-scale budget.

Providers compared (July 2026 pricing): **Render** (~$30–37/mo — true managed
Postgres with PITR, whole-stack `render.yaml`, per-service flat pricing),
**Fly.io** (best mechanics — `[processes]`, `release_command`, London — but
managed Postgres floors at $38/mo), **Railway** (~$8–15/mo usage-billed;
Postgres/Redis are template containers with volume snapshots, not PITR-managed
databases), plus DO App Platform (~$37–50) and Heroku (can't pull GHCR) as
reference points.

## Decision

### 1. Railway, three services from the one public GHCR image

Usage-based billing is the decisive fit for an always-on demo with near-zero
traffic: web + worker + beat + Postgres + Redis land at roughly $8–12/mo where
flat-per-service pricing triples that. Beat stays a **separate service**
(mirroring `docker-compose.yml`) because an idle scheduler costs cents under
usage billing — no need for the `worker -B` fold. The trade accepted: Railway's
databases are containers with daily volume snapshots (6-day retention), not
PITR-managed Postgres — tolerable for demo data that any sample job regenerates.

### 2. CD pins semver tags; `:latest` is never tracked

Railway does not watch GHCR, and `railway redeploy` re-runs the *previous*
deployment's original image reference — neither is a CD mechanism. Each release,
a workflow job calls `make deploy VERSION=<x.y.z>`
([`scripts/railway-deploy.sh`](../../scripts/railway-deploy.sh)): GraphQL
`serviceInstanceUpdate` pins `source.image` to the exact tag, then
`serviceInstanceDeployV2` creates the deployment. Every Railway deployment is
reproducible, and dashboard rollback re-runs the *old version* rather than
re-pulling whatever `:latest` means now. Railway's native image auto-update
polling (hours-delayed, maintenance-windowed) stays off as a CD path.

### 3. Web gates the fleet: pre-deploy `migrate`, `/readyz` cutover

Web deploys first with pre-deploy command `manage.py migrate` (failure aborts
the rollout — Railway keeps the previous deployment serving) and healthcheck
path `/readyz` (DB + broker reachable) gating cutover. The deploy script polls
web to `SUCCESS` before touching worker/beat, so new worker code never runs
ahead of its migrations — the runbook's "migrate as a release step, not per
replica" made executable.

### 4. Config-as-code lives in the repo, not in Railway files

`railway.json`/`toml` only applies to repo-built services; these are
image-sourced. The committed source of truth is [docs/deploy.md](../deploy.md)
(topology, env contract, provisioning, rollback), the deploy script, and the
workflow job. Dashboard-only settings (start commands, pre-deploy, healthcheck,
domain) are documented step-by-step so the platform is rebuildable from
nothing.

## Consequences

- **No PITR**: a bad write between daily snapshots is unrecoverable. Accepted
  for demo data; revisit (Render, or Railway's future managed offerings) if the
  data ever matters.
- **Deploy-time-only healthchecks**: continuous liveness is the restart policy;
  an external uptime pinger is a possible follow-up.
- The $10 hard usage cap can take the demo offline rather than overspend —
  chosen deliberately.
- Rejected: **Render** (3× the cost for this shape; PITR unneeded here),
  **Fly.io** (managed-DB economics), **tracking `:latest` + redeploy**
  (non-reproducible, staff-confirmed unreliable), **Railway repo builds**
  (the released image is already built, attested, and integration-tested — CD
  should ship *that* artifact, not rebuild it).
