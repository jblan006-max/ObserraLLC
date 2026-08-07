# Obserra EIOS — On‑Premise Installation Guide

Run the entire Obserra platform (database + backend + web app) on your own
infrastructure with a single command. **No install script is required** — the
steps below are all you need. An optional `install.sh` is included purely for
convenience.

---

## 1. Prerequisites

| Requirement | Minimum |
|-------------|---------|
| OS          | Linux / macOS / Windows (WSL2) |
| Docker      | 24+ |
| Docker Compose | v2 (`docker compose`) |
| CPU / RAM   | 2 vCPU / 4 GB (8 GB recommended) |
| Disk        | 5 GB free |

Verify Docker is ready:

```bash
docker --version
docker compose version
```

## 2. Get the code

Place the application source next to these deployment files so the folder
layout looks like this:

```
obserra/
├── backend/                 # FastAPI source
├── frontend/                # React source
└── deploy/                  # ← contents of this package
    ├── docker-compose.yml
    ├── backend.Dockerfile
    ├── frontend.Dockerfile
    ├── nginx.conf
    ├── .env.example
    ├── install.sh           # optional convenience script
    └── INSTALL.md
```

> Tip: use **Save to GitHub** (or the code‑download option) in Obserra to obtain
> the `backend/` and `frontend/` source, then drop this `deploy/` folder in.

## 3. Configure environment

```bash
cd obserra/deploy
cp .env.example .env
# edit .env — set JWT_SECRET, EMERGENT_LLM_KEY and PUBLIC_URL
```

Generate a strong secret:

```bash
openssl rand -hex 32
```

Set `PUBLIC_URL` (and `FRONTEND_URL`) to the address users will open in their
browser, e.g. `http://10.0.0.5:8080` or `https://obserra.corp.internal`.

## 4. Launch

From the project root (the folder that contains `backend/`, `frontend/` and
`deploy/`):

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

The first build takes a few minutes. When it finishes, open:

```
http://<this-machine-ip>:8080
```

### Optional convenience script

Instead of the command above you may run:

```bash
cd obserra/deploy && ./install.sh
```

## 5. First login

A seed administrator is created on first start. Change the password immediately
under **Settings → Change password**.

- Email: `admin@obserra.local` (or the seeded account documented for your build)
- You will be prompted to set a new NIST‑compliant password (≥12 chars,
  upper/lower/number/symbol).

## 6. Managing the deployment

```bash
# View logs
docker compose -f deploy/docker-compose.yml logs -f backend

# Stop
docker compose -f deploy/docker-compose.yml down

# Update after pulling new code
docker compose -f deploy/docker-compose.yml up -d --build
```

MongoDB data persists in the `obserra_mongo` Docker volume across restarts.

## 7. HTTPS (production)

For production, terminate TLS in front of the `frontend` container — e.g. put a
reverse proxy (Caddy, Traefik, or your corporate load balancer) in front of port
`8080` and point your certificate/domain at it. Update `PUBLIC_URL`/`FRONTEND_URL`
to the `https://` address.

---

## Installing the app on user devices (PWA)

Obserra is an installable Progressive Web App — no app store needed.

- **Desktop (Chrome/Edge):** open the site → click the **Install** icon in the
  address bar, or use the in‑app **Install Obserra** banner.
- **Android (Chrome):** tap the **Install Obserra** banner, or menu → *Add to
  Home screen*.
- **iOS/iPadOS (Safari):** Share → **Add to Home Screen**.

Once installed it launches full‑screen like a native app and works across
desktop, tablet and mobile.
