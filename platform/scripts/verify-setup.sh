#!/usr/bin/env bash
# Verifies a fresh clone can go from zero to a running dev server using only
# documented steps and the .env.example defaults (copied to .env). Exits
# non-zero on the first failure so CI / a new contributor gets a clear signal.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
RESET='\033[0m'

step() { echo -e "\n${BOLD}==> $1${RESET}"; }
ok()   { echo -e "${GREEN}✓ $1${RESET}"; }
fail() { echo -e "${RED}✗ $1${RESET}"; exit 1; }

# --- 1. Node version -------------------------------------------------------
step "Checking Node.js version (>=20 required)"
if ! command -v node >/dev/null 2>&1; then
  fail "node is not installed. Install Node.js 20+ from https://nodejs.org."
fi
NODE_MAJOR=$(node -p "process.versions.node.split('.')[0]")
if [ "$NODE_MAJOR" -lt 20 ]; then
  fail "Node.js 20+ required, found $(node -v)."
fi
ok "Node.js $(node -v)"

# --- 2. Package manager ------------------------------------------------------
step "Checking pnpm"
if ! command -v pnpm >/dev/null 2>&1; then
  fail "pnpm is not installed. Install with: corepack enable && corepack prepare pnpm@latest --activate"
fi
ok "pnpm $(pnpm -v)"

# --- 3. .env ----------------------------------------------------------------
step "Ensuring .env exists"
if [ ! -f .env ]; then
  cp .env.example .env
  ok "Created .env from .env.example (dummy/dev defaults)"
else
  ok ".env already exists"
fi
set -a
# shellcheck disable=SC1091
source .env
set +a

# --- 4. Database --------------------------------------------------------
step "Checking Postgres connectivity at DATABASE_URL"
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "Starting Postgres + Redis via docker compose..."
  docker compose up -d postgres redis
  ok "docker compose services started"
else
  echo "Docker not available/running — assuming a Postgres instance is already reachable at DATABASE_URL"
fi

DB_READY=false
for _ in $(seq 1 20); do
  if pnpm --filter @identity/api exec prisma db execute --stdin <<<"SELECT 1;" >/dev/null 2>&1; then
    DB_READY=true
    break
  fi
  sleep 1
done
if [ "$DB_READY" != "true" ]; then
  fail "Could not reach Postgres at DATABASE_URL. Start it (docker compose up -d postgres) or update .env."
fi
ok "Postgres is reachable"

# --- 5. Install dependencies -------------------------------------------------
step "Installing dependencies (pnpm install)"
pnpm install
ok "Dependencies installed"

# --- 6. Migrate + generate ---------------------------------------------------
step "Running Prisma migrations"
pnpm --filter @identity/api exec prisma migrate deploy
pnpm --filter @identity/api exec prisma generate
ok "Database schema is up to date"

# --- 7. Seed ------------------------------------------------------------
step "Seeding demo data"
pnpm db:seed
ok "Seed data loaded (demo@identity.local / password123)"

# --- 8. Unit tests ------------------------------------------------------
step "Running unit tests (shared calculation logic)"
pnpm --filter @identity/shared test
pnpm --filter @identity/api test
ok "Unit tests passed"

# --- 9. Boot the dev server and confirm it responds -------------------------
step "Booting the web app dev server and checking it responds"
PORT="${VERIFY_PORT:-3300}"
# The `&` must be outside the subshell parens so `$!` (captured in the
# parent shell, which has `set -u`) actually refers to this job.
(cd apps/web && exec pnpm exec next dev -p "$PORT") > /tmp/identity-verify-dev.log 2>&1 &
DEV_PID=$!

READY=false
# First compile can take a while (cold Next.js cache, many workspace
# packages) — allow up to 3 minutes, and bound each curl so one slow
# in-flight request can't eat the whole budget.
for _ in $(seq 1 90); do
  CODE=$(curl -s --max-time 2 -o /dev/null -w "%{http_code}" "http://localhost:$PORT/" || true)
  if [ "$CODE" = "200" ]; then
    READY=true
    break
  fi
  sleep 2
done

if [ "$READY" != "true" ]; then
  echo "--- dev server log ---"
  tail -n 60 /tmp/identity-verify-dev.log || true
  kill "$DEV_PID" >/dev/null 2>&1 || true
  fail "Dev server did not respond with HTTP 200 on http://localhost:$PORT/ within 3 minutes."
fi
ok "Dev server responded with HTTP 200 on http://localhost:$PORT/"

# Best-effort shutdown of the dev server we started.
pkill -P "$DEV_PID" >/dev/null 2>&1 || true
kill "$DEV_PID" >/dev/null 2>&1 || true

echo -e "\n${GREEN}${BOLD}All checks passed.${RESET} Run 'pnpm dev' and open http://localhost:3000"
