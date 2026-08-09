#!/usr/bin/env bash
# Obserra SAP UAC — one-click on-premise installer.
# Run this from the extracted "obserra-sap-uac/" folder:  ./install.sh
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

say(){ printf "\033[36m==>\033[0m %s\n" "$1"; }
err(){ printf "\033[31m!!\033[0m %s\n" "$1" >&2; }

VER="$([ -f VERSION ] && cat VERSION || echo '?')"
BUILT="$([ -f BUILD_INFO ] && (grep '^built=' BUILD_INFO | cut -d= -f2) || echo '')"
say "Obserra SAP UAC — one-click on-premise installer (v${VER}${BUILT:+, built ${BUILT}})"

command -v docker >/dev/null 2>&1 || { err "Docker is required — see https://docs.docker.com/get-docker/"; exit 1; }
docker compose version >/dev/null 2>&1 || { err "Docker Compose v2 is required (the 'docker compose' command)."; exit 1; }

COMPOSE="deploy/docker-compose.yml"
ENV_FILE="deploy/.env"

if [ ! -f "$ENV_FILE" ]; then
  cp deploy/.env.example "$ENV_FILE"
  if command -v openssl >/dev/null 2>&1; then
    SECRET="$(openssl rand -hex 32)"
  else
    SECRET="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  fi
  # Portable in-place edit (works with both GNU and BSD sed).
  sed -i.bak "s|^JWT_SECRET=.*|JWT_SECRET=${SECRET}|" "$ENV_FILE" && rm -f "${ENV_FILE}.bak"
  say "Created ${ENV_FILE} with a freshly generated JWT_SECRET."
else
  say "Using existing ${ENV_FILE}."
fi

PUBLIC_URL="$(grep -E '^PUBLIC_URL=' "$ENV_FILE" | cut -d= -f2- || true)"
PUBLIC_URL="${PUBLIC_URL:-http://localhost:8080}"
PUBLIC_URL="${PUBLIC_URL%/}"

say "Building and starting containers — first run downloads images and builds the app (a few minutes)…"
docker compose -f "$COMPOSE" --env-file "$ENV_FILE" up -d --build

say "Waiting for the app to become healthy…"
ok=0
for _ in $(seq 1 90); do
  if curl -fsS "${PUBLIC_URL}/api/health" 2>/dev/null | grep -q '"status":"ok"'; then ok=1; break; fi
  sleep 3
done

if [ "$ok" != "1" ]; then
  err "Containers started but the health check timed out."
  echo "   Check logs:  docker compose -f ${COMPOSE} logs -f backend"
  echo "   Health URL:  ${PUBLIC_URL}/api/health"
  exit 0
fi

say "Obserra SAP UAC is up at ${PUBLIC_URL}"

# --- First-run administrator (only while the instance has no users yet) ---
STATUS="$(curl -fsS "${PUBLIC_URL}/api/auth/bootstrap-status" 2>/dev/null || echo '')"
if printf '%s' "$STATUS" | grep -q '"initialized":false'; then
  echo
  read -r -p "   Load the demo SAP dataset so dashboards are populated? [Y/n]: " DEMO_ANS
  case "${DEMO_ANS:-Y}" in [Nn]*) SEED_DEMO=false ;; *) SEED_DEMO=true ;; esac

  say "Create the first administrator account:"
  read -r -p "   Admin email [jblan2026@gmail.com]: " ADMIN_EMAIL
  ADMIN_EMAIL="${ADMIN_EMAIL:-jblan2026@gmail.com}"
  ADMIN_PW=""; ADMIN_PW2="x"
  while [ -z "$ADMIN_PW" ] || [ "$ADMIN_PW" != "$ADMIN_PW2" ]; do
    read -r -s -p "   Admin password (min 15 chars, upper/lower/number/symbol): " ADMIN_PW; echo
    read -r -s -p "   Confirm password: " ADMIN_PW2; echo
    [ "$ADMIN_PW" != "$ADMIN_PW2" ] && err "Passwords did not match — try again."
  done
  RESP="$(curl -sS -X POST "${PUBLIC_URL}/api/auth/bootstrap-admin" \
            -H 'Content-Type: application/json' \
            -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PW}\",\"name\":\"Administrator\",\"seed_demo\":${SEED_DEMO}}" || true)"
  if printf '%s' "$RESP" | grep -q '"email"'; then
    say "Administrator ${ADMIN_EMAIL} created. Sign in at ${PUBLIC_URL}"
    [ "$SEED_DEMO" = "true" ] && echo "   Demo SAP dataset loaded — dashboards are populated."
  else
    err "Could not create the admin automatically: ${RESP}"
    echo "   Create it from the app's Create Account screen instead."
  fi
else
  echo "   Sign in at ${PUBLIC_URL} (an account already exists on this instance)."
fi
