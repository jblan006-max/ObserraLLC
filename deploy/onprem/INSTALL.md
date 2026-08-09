# Obserra SAP UAC — On‑Premise Installer

Run the entire **Obserra SAP User Access Control** platform (database + backend +
web app) on your own infrastructure with **one command**. This package is
**self‑contained** — the full application source (`backend/` and `frontend/`) is
bundled alongside the Docker deployment files, so there is nothing else to
download.

```
obserra-sap-uac/
├── backend/            # FastAPI source (bundled)
├── frontend/           # React source (bundled)
├── install.sh          # ← one-click installer (run this)
└── deploy/
    ├── docker-compose.yml
    ├── docker-compose.https.yml     # optional HTTPS via Caddy
    ├── docker-compose.traefik.yml   # optional HTTPS via Traefik
    ├── backend.Dockerfile
    ├── frontend.Dockerfile
    ├── nginx.conf
    ├── Caddyfile
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
2. Create `deploy/.env` from the template and **auto‑generate a strong
   `JWT_SECRET`** (no manual editing required).
3. Build and start MongoDB, the FastAPI backend and the React web app.
4. Wait until the app is healthy and print the URL to open.

When it finishes, open:

```
http://<this-machine-ip>:8080
```

> Prefer to do it by hand? See **Manual launch** below.

## 3. First login

On first launch, open the app and click **Create Account** to register your
organization and its first user.

To grant that user the **Admin** role (Settings, Team, Deployment &
Documentation), promote it once in the database:

```bash
docker compose -f deploy/docker-compose.yml exec mongodb \
  mongosh obserra_sap_uac --eval 'db.users.updateOne({email:"you@company.com"},{$set:{role:"admin"}})'
```

You'll be asked to set a NIST‑compliant password (≥12 chars, with
upper/lower/number/symbol).

## 4. AI features (optional)

The AI Advisor, SoD narratives and board summaries use an LLM. Paste your key
into `deploy/.env` and restart:

```bash
EMERGENT_LLM_KEY=your-key-here
```
```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d
```
Leaving it blank keeps every non‑AI feature fully functional.

## 5. Managing the deployment

```bash
# View logs
docker compose -f deploy/docker-compose.yml logs -f backend

# Stop
docker compose -f deploy/docker-compose.yml down

# Update after replacing the source
docker compose -f deploy/docker-compose.yml up -d --build
```

MongoDB data persists in the `obserra_uac_mongo` Docker volume across restarts.

## Manual launch

If you'd rather not use `install.sh`:

```bash
cd obserra-sap-uac
cp deploy/.env.example deploy/.env
# set a strong JWT_SECRET (openssl rand -hex 32) and, optionally, EMERGENT_LLM_KEY
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

Set `PUBLIC_URL` (and `FRONTEND_URL`) to the address users will open in their
browser, e.g. `http://10.0.0.5:8080` or `https://sapuac.corp.internal`.

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

Caddy obtains and renews the certificate automatically and proxies to the app.
Open `https://<DOMAIN>`. (Uses `deploy/Caddyfile`.)

### Option B — Traefik

```bash
docker compose -f deploy/docker-compose.traefik.yml --env-file deploy/.env up -d --build
```

Traefik provisions the cert, redirects HTTP→HTTPS, and routes to the app via
labels.

> Both HTTPS compose files are **self‑contained** (they include MongoDB, backend
> and frontend) — use them *instead of* the plain `docker-compose.yml`, not
> alongside it.

---

## Installing the app on user devices (PWA)

Obserra SAP UAC is an installable Progressive Web App — no app store needed.

- **Desktop (Chrome/Edge):** open the site → click the **Install** icon in the
  address bar, or use the in‑app **Install** banner.
- **Android (Chrome):** tap the **Install** banner, or menu → *Add to Home
  screen*.
- **iOS/iPadOS (Safari):** Share → **Add to Home Screen**.

Once installed it launches full‑screen like a native app and works across
desktop, tablet and mobile.
