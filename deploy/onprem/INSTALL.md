# Obserra SAP UAC — On‑Premise Installer

Run the entire **Obserra SAP User Access Control** platform (database + backend +
web app) on your own infrastructure with **one command**. This package is
**self‑contained** — the full application source (`backend/` and `frontend/`) is
bundled alongside the Docker deployment files, so there is nothing else to
download.

The exact version and build date you downloaded are recorded in `VERSION` and
`BUILD_INFO`, and `install.sh` prints them at the top of every run.

```
obserra-sap-uac/
├── VERSION             # e.g. 1.0.0
├── BUILD_INFO          # version + build date
├── install.sh          # ← one-click installer (run this)
├── backend/            # FastAPI source (bundled)
├── frontend/           # React source (bundled)
└── deploy/
    ├── docker-compose.yml
    ├── docker-compose.https.yml     # optional HTTPS via Caddy
    ├── docker-compose.traefik.yml   # optional HTTPS via Traefik
    ├── backend.Dockerfile
    ├── frontend.Dockerfile
    ├── nginx.conf
    ├── Caddyfile
    ├── build-wheelhouse.sh          # optional — for fully air-gapped installs
    ├── wheels/                      # bundled emergentintegrations wheel (+ your offline wheelhouse)
    ├── .env.example
    └── INSTALL.md      # this file
```

---

## 1. Prerequisites

| Requirement    | Minimum |
|----------------|---------|
| OS             | Linux / macOS / Windows (WSL2) |
| Docker         | 24+ |
| Docker Compose | v2 (`docker compose`) |
| CPU / RAM      | 2 vCPU / 4 GB (8 GB recommended) |
| Disk           | 5 GB free |

Verify Docker is ready:

```bash
docker --version
docker compose version
```

## 2. One‑click install

From the extracted `obserra-sap-uac/` folder:

```bash
./install.sh
```

That's it. The installer will:

1. Check Docker & Compose are present.
2. Create `deploy/.env` from the template and **auto‑generate a strong `JWT_SECRET`**.
3. Build and start MongoDB, the FastAPI backend and the React web app.
4. Wait until the app is healthy (`/api/health`), then ask whether to **load the
   demo SAP dataset** (so dashboards are populated) and **prompt you to create the
   first administrator** (email + password) — no database commands required.
5. Print the URL to open.

When it finishes, open:

```
http://<this-machine-ip>:8080
```

> Prefer to do it by hand? See **Manual launch** below.

## 3. AI features (optional)

The AI Advisor, SoD narratives and board summaries use an LLM. Paste your key
into `deploy/.env` and restart:

```bash
EMERGENT_LLM_KEY=your-key-here
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d
```

Leaving it blank keeps every non‑AI feature fully functional.

## 4. Fully offline / air‑gapped installs

The bundled `deploy/wheels/` already contains the `emergentintegrations` wheel, so
the build never needs the private package index — only public PyPI for the rest.

For a host with **no internet at all**, pre‑build a complete wheelhouse on a
connected machine of the **same CPU architecture and Python 3.11**, then copy the
package across:

```bash
cd obserra-sap-uac
deploy/build-wheelhouse.sh        # downloads every dependency into deploy/wheels/ and marks it OFFLINE
# copy the whole obserra-sap-uac/ folder to the air-gapped host, then:
./install.sh
```

When `deploy/wheels/OFFLINE` is present the backend image installs **everything**
from the local wheelhouse with no network access.

## 5. Managing the deployment

```bash
docker compose -f deploy/docker-compose.yml logs -f backend   # logs
docker compose -f deploy/docker-compose.yml down              # stop
docker compose -f deploy/docker-compose.yml up -d --build     # update after replacing source
```

MongoDB data persists in the `obserra_uac_mongo` Docker volume across restarts.

### Prebuilt images (GHCR — no local build)

Every tagged release also publishes prebuilt `backend` and `frontend` images to the
GitHub Container Registry, so you can run without building locally:

```bash
IMAGE_PREFIX=ghcr.io/your-org/obserra-sap-uac IMAGE_TAG=v1.0.0 \
  docker compose -f deploy/docker-compose.ghcr.yml --env-file deploy/.env up -d
```

`GET /api/health` reports readiness (`{"status":"ok"}`) for load balancers and uptime
checks. Admins are shown an in‑app banner when a newer release is available (set
`UPDATE_MANIFEST_URL` in `deploy/.env` to a JSON `{ "version": "1.1.0", "url": "…" }`).

## Manual launch

```bash
cd obserra-sap-uac
cp deploy/.env.example deploy/.env
# set a strong JWT_SECRET (openssl rand -hex 32) and, optionally, EMERGENT_LLM_KEY
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

Set `PUBLIC_URL` (and `FRONTEND_URL`) to the address users will open in their
browser, e.g. `http://10.0.0.5:8080` or `https://sapuac.corp.internal`. Create the
first admin from the app's **Create Account** screen, or call
`POST /api/auth/bootstrap-admin` (works only while no user exists yet).

## 6. HTTPS (production)

Two ready‑made options give you a valid TLS certificate automatically (Let's
Encrypt). Both require a **public DNS record for your domain pointing at this
host** and **ports 80 and 443 open**. In `deploy/.env` set:

```bash
DOMAIN=sapuac.yourcompany.com
ACME_EMAIL=admin@yourcompany.com
PUBLIC_URL=https://sapuac.yourcompany.com   # must match DOMAIN
FRONTEND_URL=https://sapuac.yourcompany.com
```

### Option A — Caddy (recommended, simplest)

```bash
docker compose -f deploy/docker-compose.https.yml --env-file deploy/.env up -d --build
```

### Option B — Traefik

```bash
docker compose -f deploy/docker-compose.traefik.yml --env-file deploy/.env up -d --build
```

> Both HTTPS compose files are **self‑contained** (they include MongoDB, backend
> and frontend) — use them *instead of* the plain `docker-compose.yml`.

---

## Installing the app on user devices (PWA)

Obserra SAP UAC is an installable Progressive Web App — no app store needed.

- **Desktop (Chrome/Edge):** open the site → click the **Install** icon in the
  address bar, or use the in‑app **Install** banner.
- **Android (Chrome):** tap the **Install** banner, or menu → *Add to Home screen*.
- **iOS/iPadOS (Safari):** Share → **Add to Home Screen**.
