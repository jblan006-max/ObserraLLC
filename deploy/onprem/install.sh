#!/usr/bin/env bash
# Obserra EIOS — optional convenience installer.
# This is NOT required; you can run the docker compose command from INSTALL.md
# directly. It simply checks prerequisites and brings the stack up.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"

echo "==> Obserra on-premise installer"

command -v docker >/dev/null 2>&1 || { echo "Docker is required. See https://docs.docker.com/get-docker/"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is required."; exit 1; }

if [ ! -f "$here/.env" ]; then
  cp "$here/.env.example" "$here/.env"
  echo "==> Created deploy/.env from template. Edit it to set JWT_SECRET / EMERGENT_LLM_KEY / PUBLIC_URL, then re-run."
  exit 0
fi

echo "==> Building and starting containers..."
docker compose -f "$here/docker-compose.yml" --env-file "$here/.env" up -d --build

echo "==> Done. Open the PUBLIC_URL from your .env (default http://localhost:8080)."
