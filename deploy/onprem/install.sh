#!/usr/bin/env bash
# Obserra SAP UAC — one-click on-premise installer.
# Run this from the extracted "obserra-sap-uac/" folder:  ./install.sh
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

say(){ printf "\033[36m==>\033[0m %s\n" "$1"; }
err(){ printf "\033[31m!!\033[0m %s\n" "$1" >&2; }

say "Obserra SAP UAC — one-click on-premise installer"

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

say "Building and starting containers — first run downloads images and builds the app (a few minutes)…"
docker compose -f "$COMPOSE" --env-file "$ENV_FILE" up -d --build

say "Waiting for the app to become healthy…"
ok=0
for _ in $(seq 1 90); do
  if curl -fsS "${PUBLIC_URL%/}/" >/dev/null 2>&1; then ok=1; break; fi
  sleep 3
done

echo
if [ "$ok" = "1" ]; then
  say "Obserra SAP UAC is up and running."
  echo "   Open:          ${PUBLIC_URL}"
  echo "   First run:      click 'Create Account' to register your organization."
  echo "   Make an admin:  docker compose -f ${COMPOSE} exec mongodb mongosh obserra_sap_uac --eval 'db.users.updateOne({email:\"you@company.com\"},{\$set:{role:\"admin\"}})'"
else
  err "Containers started but the health check timed out."
  echo "   Check logs with: docker compose -f ${COMPOSE} logs -f backend"
  echo "   (If PUBLIC_URL is a non-local domain, open it in a browser to confirm.)"
fi
