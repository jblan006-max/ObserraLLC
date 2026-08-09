#!/usr/bin/env bash
# Obserra SAP UAC — build a FULLY offline Python wheelhouse for air-gapped installs.
#
# Run this on an internet-connected machine with the SAME CPU architecture and
# Python 3.11 as your target Docker host. Afterwards copy the whole package to the
# air-gapped host and run ./install.sh — the build then installs every dependency
# from deploy/wheels/ with no network access.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$here/wheels"

echo "==> Downloading application dependencies…"
pip download -r "$here/../backend/requirements.txt" -d "$here/wheels"

echo "==> Downloading emergentintegrations…"
pip download emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ -d "$here/wheels"

touch "$here/wheels/OFFLINE"
echo "==> Wheelhouse ready: $(ls "$here"/wheels/*.whl 2>/dev/null | wc -l) wheels."
echo "    The next 'docker compose build' (or ./install.sh) installs fully offline."
