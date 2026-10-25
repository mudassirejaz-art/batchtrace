# BatchTrace — single VPS deployment skeleton (Step 49)

This package **only creates deployment files**. It does not start containers, apply database migrations, expose a domain, or modify BatchTrace source files. Tested local release commit: `6e27e93`.

Architecture: public **Caddy** (80/443, React static files + `/api` reverse proxy) → private **FastAPI** (8000) → private **PostgreSQL 16**. Only Caddy ports are published. Caddy obtains TLS certificates for a configured public domain. `db_net` has no external networking.

## Prerequisites

- Linux VPS with Docker Engine and Docker Compose plugin, DNS A/AAAA record for the domain pointing at the VPS, and ports 80 and 443 open. Do not open PostgreSQL 5432 or FastAPI 8000 publicly.
- Git checkout containing BatchTrace backend and frontend. Run commands from **repo root**.
- Production data must be separate from the developer's `batchtrace_db`; never restore local demo data into production.
- Stable off-host backups and monitoring need a separate deployment plan. A local restore test is not production disaster recovery.

## 1. Secrets on the VPS

Generate fresh credentials **only on the actual VPS**.
Never copy local development secrets into production.

```bash
cd ~/batchtrace

if [ -e deployment/.env ]; then
  echo "STOP: Production .env already exists"
  exit 1
fi

umask 077
cp deployment/.env.example deployment/.env
chmod 600 deployment/.env

python3 - <<'PY'
from pathlib import Path
import secrets

path = Path("deployment/.env")
content = path.read_text()

for key, size in [
    ("POSTGRES_PASSWORD", 36),
    ("JWT_SECRET", 48),
]:
    placeholder = f"{key}=\n"
    if content.count(placeholder) != 1:
        raise SystemExit(f"STOP: Unexpected {key} template")

    content = content.replace(
        placeholder,
        f"{key}={secrets.token_urlsafe(size)}\n",
        1,
    )

path.write_text(content)
path.chmod(0o600)

print("PASS: Unique production secrets generated")
print("Secret values were not displayed")
PY
```

Replace `SITE_DOMAIN=batchtrace.example.com` in
`deployment/.env` with the real production hostname.
Configure DNS before starting the public web service.
Never commit or share `deployment/.env`.

## 2. Validate config, without starting containers

```bash
docker compose --env-file deployment/.env -f deployment/compose.yaml config --quiet
```

Run from the repository root. The unsuppressed `docker compose config` output can contain secrets, so never paste it into chat.

## 3. Deployment (requires explicit approval for production database operations)

These are instructions for the approved operator, NOT commands automatically executed by this package:

```bash
# Review Dockerfiles before building.
docker compose --env-file deployment/.env -f deployment/compose.yaml build

# Database initialization / schema changes require separate explicit approval:
docker compose --env-file deployment/.env -f deployment/compose.yaml up -d db
# With explicit schema-migration approval ONLY:
docker compose --env-file deployment/.env -f deployment/compose.yaml run --rm backend alembic upgrade head
# Only after migration and backup review:
docker compose --env-file deployment/.env -f deployment/compose.yaml up -d backend web
```

`alembic upgrade head` **changes the database schema**. Do not run without checking the target and obtaining explicit approval. No automatic migrations run when the API container starts.

## 4. Post-deployment checks

```bash
curl -I https://YOUR_REAL_DOMAIN/
curl -i https://YOUR_REAL_DOMAIN/api/v1/health
curl -I https://YOUR_REAL_DOMAIN/docs  # Expect 404
```

Confirm browser flows with an authorized test workspace, firewall, TLS issuance, absence of mixed content, server/DB monitoring, restore procedure and backups stored **off the VPS**. Never confuse internal credit records with actual bank verification.

## Caveats

- Strict-Transport-Security with 1-year max-age should only be used once HTTPS is stable and the deployment hostname is decided. Caddy serves HTTPS automatically for a valid public hostname.
- A browser-tested frontend CSP has not been added; evaluate separately before external release.
- Container vulnerability scanning, data retention, rate limits behind a trusted reverse proxy, capacity limits, production log management and independent backups remain separate release steps.
- `docker compose config --quiet` validates Compose interpolation/schema only; actual image builds and Caddy runtime syntax still require validation in the target Docker environment.
