# 17 — Deployment Guide

## 1. Environments

| Env | Location | Stack | Purpose |
|---|---|---|---|
| dev | laptop | host-run API/web, docker PG+Redis | fast iteration (`make dev`) |
| staging | EU VPS | compose full stack, seeded golden set | CI deploys, eval, partner pilots |
| prod | EU VPS (DE/FR) -> managed EU cloud | compose -> k3s/Helm | GA |

All regions: **EU (GDPR)**: Hetzner Falkenstein/FSN (DE) or OVH Gravelines (FR). Storage/DB region = tenant residency region.

## 2. Topology (single VPS, MVP)

```
Caddy (TLS, reverse proxy, auto-HTTPS, rate limit pass-through)
 ├─ apps/web        :3000   (Next.js standalone)
 ├─ api             :8000   (uvicorn, 2 workers)      (health /healthz)
 ├─ worker          :—      (celery, 2 concurrent)     (health /healthz)
 ├─ vies-proxy      :8010   (cached VAT checks)        (health /healthz)
 ├─ postgres:16     :5432
 ├─ redis:7         :6379
 ├─ minio           :9000/9001
 └─ exporter/otel   (metrics, traces)
```
Caddy is the only public entry. API and web on internal network. Volumes: `pgdata`, `redis`, `minio`, `models`.

## 3. VPS sizing (cost estimate)

| Load | CPU | RAM | Disk | €/mo (Hetzner) |
|---|---|---|---|---|
| dev/staging | 2–4 vCPU | 8 GB | 80 GB | ~12–25 |
| MVP prod ≤1k/day | 4 vCPU | 16 GB | 120 GB (SSD) | ~35–45 |
| 10k/day | 8 vCPU | 32 GB + 1 GPU node (optional) | 250 GB | ~60–120 + GPU ~100 |
| 100k/day | 3–5 nodes | — | — | managed cloud |

Backups: nightly `pg_dump` (or wal-g WAL archiving) to object storage (MinIO or Hetzner Storage Box), retention 14d; restore drill documented + tested quarterly. Redis: AOF + RDB snapshots. MinIO: mirror to second region optional.

## 4. Compose layout

- `docker-compose.yml` — full stack (staging/prod profile)
- `docker-compose.override.yml` — dev: minio optional, hot-reload mounts, worker auto-reload
- `docker-compose.ci.yml` — postgres+redis only for integration tests
- Service env from `.env` (gitignored); `.env.example` documents every var
- Healthchecks on every service; `restart: unless-stopped`; depends_on with condition health
- Logs: JSON to stdout; docker log rotation (max 50 MB x 5); Sentry for errors

## 5. Build & release

- Next.js `output: standalone`; Python images python:3.12-slim (paddle extra `--platform linux/amd64`); multi-stage to keep images lean.
- Image tags `git-sha`; `deploy.yml` on main: build -> push (registry: GHCR or local) -> ssh `compose pull && compose up -d`.
- Migrations: Alembic `upgrade head` as a one-shot job before app rollout (idempotent, backward-compatible migrations only; squash pre-GA).
- Zero-downtime: api runs 2 replicas behind Caddy; worker drains gracefully (`CELERY_ACK_LATE`, prefetch 1).

## 6. Caddyfile essentials

```
invoiceiq.example.eu {
    reverse_proxy /api/* :8000
    reverse_proxy :3000
    header { -Server }
    encode zstd gzip
}
healthz endpoint on api/worker for compose healthchecks.
```

## 7. Observability

- Prometheus (scrape api+worker+postgres-exporter+redis-exporter+minio), Grafana (dashboards: pipeline latency, STP rate, cost/invoice, queue depth, error budget), alert rules -> ntfy/email.
- OpenTelemetry -> console (dev) / collector -> Grafana Tempo (staging+).
- Sentry (python + nextjs) with `release = git-sha`.

## 8. Secrets

- `.env` on VPS (root-only), sourced by compose; `ENCRYPTION_KEY`, `SECRET_KEY`, DB creds, LLM keys, Stripe (P2), webhook secrets.
- No secrets in repo; CI uses GH secrets; P4: SOPS/Docker secrets + BYOK.

## 9. Migration path to K8s (P4)

k3s single-node -> managed (AKS/EKS/GKE EU region) or Fly/Render/OVH. Same compose services become Deployments; `infra/deploy/k8s/` holds manifests (HPA on queue depth, PDB, resource requests/limits, PVCs or managed PG). Partitioned queues (`ocr/extract/validate/export`) make worker pools independently scalable.

## 10. Dev machine setup (this laptop — 16 GB RAM, 22 GB free)

- Docker Desktop (WSL2) for **postgres + redis only**. Run API + worker + Next.js on the host (faster iteration, less RAM).
- `make dev` brings up: docker pg/redis, alembic upgrade, uvicorn --reload, celery worker, next dev.
- **MinIO optional** — dev uses `storage.local` (disk backend) to save RAM; prod uses `storage.s3`.
- **Free disk first:** PaddleOCR models + node_modules + Docker images need ~10 GB; clean `C:` or relocate Docker data to `D:`/external SSD. If <8 GB free: skip MinIO, limit worker concurrency to 2, and close heavy apps during OCR runs.
- **GPU (optional):** PaddleOCR CPU is enough for dev; WSL2 CUDA setup only if running VLM work.

## 11. Go-live checklist (staging → prod)

- [ ] backups verified + restore drill passed
- [ ] Sentry/alerting wired; on-call = founder (pagertree/ntfy)
- [ ] rate limits + auth brute-force protections on
- [ ] security checklist `docs/18` + GDPR checklist `docs/19` signed
- [ ] eval gate green for last model/prompt/OCR versions
- [ ] cost telemetry dashboards confirmed (cost/invoice within budget)
- [ ] DNS + TLS + SPF/DKIM/DMARC for email domain (P2 ingest)
- [ ] legal: ToS/Privacy/DPA published; EU-only subprocessors list
