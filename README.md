# Personal Engineering Dashboard

Desktop-first, mobile-ready local dashboard built with FastAPI, Jinja2, HTMX, Bootstrap, SQLite, and psutil.

## Current MVP

- Overview page with project/application/priority summary cards
- Current project tracking
- Job application pipeline with applied dates, follow-up dates, and source tracking
- Stage-distribution chart and follow-up watchlist on the overview
- Job Application Kanban with pipeline stage aging and HTMX stage moves
- Learning tracker with active certifications, course links, and next actions
- Financials tracker with local account balances, inflow/outflow history, and monthly payments
- Today's attention queue with HTMX completion
- Live CPU / memory / disk / OS metrics
- Responsive Bootstrap desktop layout + mobile offcanvas navigation
- SQLite persistence
- `/health` endpoint
- Local-only default run command
- Optional Docker Compose deployment path for laptop and Raspberry Pi

## Windows setup

Recommended folder:

```powershell
C:\work\local\ai-dashboard
```

Open PowerShell:

```powershell
cd C:\work\local\ai-dashboard
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Health check:

```text
http://127.0.0.1:8000/health
```

The dashboard reads shared projects, applications, learning records, and priorities through the Personal Data Layer API. It does not open its former local dashboard database. The legacy `data/` directory remains ignored by Git so private records are never included in the public repository.

## Personal Data Layer connection

Start the Personal Data Layer separately before opening the dashboard:

```powershell
cd C:\work\local\personal_data_layer
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8100
```

The dashboard uses `http://127.0.0.1:8100/api/v1` by default. To use another trusted endpoint, set `PERSONAL_DATA_BASE_URL` before starting the dashboard. The first shared-data API is intentionally read-only: add/edit controls are disabled until the layer provides authenticated write endpoints. Financial records are not displayed through this integration until a dedicated finance API and authorization model are approved.

## Homelab Host Observer

The Homelab tab gets machine metrics and listening-service status through a separate, read-only Host Observer. This is the translation layer: it uses the same API contract on Windows, Linux, and Raspberry Pi OS, so the dashboard never needs device-specific process commands or host-level container permissions.

Start it on the device you want to monitor:

```powershell
cd C:\work\local\ai-dashboard
.\.venv\Scripts\python -m uvicorn host_observer.main:app --host 127.0.0.1 --port 8200
```

The dashboard uses `http://127.0.0.1:8200/api/v1` when it runs directly, or `http://host.docker.internal:8200/api/v1` in Docker. It is read-only and binds to loopback by default. If a Raspberry Pi deployment needs a different private route, set `HOST_OBSERVER_BASE_URL` rather than changing dashboard code.

Optional per-device service aliases can be supplied without changing code:

```powershell
$env:HOST_OBSERVER_SERVICE_LABELS = '{"8000":"Personal Dashboard","8100":"Personal Data Layer","8200":"Host Observer","11434":"Ollama"}'
```

## Docker deployment

Docker is recommended as the **portable deployment path** for the eventual Raspberry Pi 5. It gives the laptop and Pi the same runtime while keeping the dashboard as a stateless client of the separately run Personal Data Layer. Direct Python remains the faster option for day-to-day development because it supports reload mode.

With Docker Desktop running on Windows, start the dashboard with:

```powershell
docker compose up --build
```

It is bound to `127.0.0.1:8000` by default, so it remains available only on the machine running it. The container calls the Personal Data Layer and Host Observer through `host.docker.internal` by default and never receives a mounted database, job-posting folder, Docker socket, or host PID namespace. On Linux or Raspberry Pi, set `PERSONAL_DATA_BASE_URL` and `HOST_OBSERVER_BASE_URL` to the trusted private API addresses or service names used by your deployment.

Useful commands:

```powershell
docker compose up -d --build
docker compose logs -f
docker compose down
```

To test from a phone on a trusted LAN, explicitly expose the service before starting it:

```powershell
$env:DASHBOARD_BIND_ADDRESS = "0.0.0.0"
docker compose up -d --build
```

Allow the port through Windows Firewall only for private networks. Do not expose it through router port forwarding.

## Testing from your Android phone later

While still developing on Windows, you can bind to the laptop's LAN interface:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then browse to the laptop's private Wi-Fi IP, for example `http://192.168.x.x:8000`.

Only do this on a trusted private network. Windows Firewall may ask whether Python/Uvicorn can accept private-network connections; do not allow public-network access.

## Raspberry Pi migration path

The application is deliberately portable. Docker Compose is the recommended way to run it on the Pi:

1. Install 64-bit Raspberry Pi OS and Docker Engine with the Compose plugin.
2. Deploy the Personal Data Layer as a separate private service, including its own controlled data volume and backups.
3. Run the Host Observer on the Pi itself and keep it bound to private loopback, or provide it through an equally private service route.
4. Set `PERSONAL_DATA_BASE_URL` and `HOST_OBSERVER_BASE_URL` to those service addresses.
5. Start the dashboard with `docker compose up -d --build` for Pi-local access, or set `DASHBOARD_BIND_ADDRESS=0.0.0.0` for trusted-LAN access.
6. Keep it LAN-only initially; add Tailscale later for remote access.
7. Back up the Personal Data Layer according to its own backup plan; the dashboard itself is stateless.
8. Optionally self-host Bootstrap, HTMX, and ApexCharts assets so the UI does not depend on CDN access.

The official Python base image is multi-architecture, so the same Dockerfile builds on an x86 Windows laptop and a 64-bit ARM Raspberry Pi 5. `psutil` automatically reads metrics from Windows now and Linux/Raspberry Pi OS later.

## Suggested next increments

- Edit/delete project and application records
- Shared-data importer for the Job-Hunt Agent's JSON records
- Application follow-up notifications / overdue alerts
- Project milestones and recent Git activity
- Learning/certification tracker
- Calendar/interview panel
- Login/authentication before any remote access
- PWA manifest and service worker for Android home-screen installation
- Backup/export to JSON/CSV
- Pi service/container status panel
