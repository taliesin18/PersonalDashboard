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

The first launch creates `data/dashboard.db` and inserts starter data. The Financials tab creates its separate, local-only `data/finance.db` when it is first opened. Everything in `data/` is intentionally excluded from Git, so your records are never included in the public repository.

## Docker deployment

Docker is recommended as the **portable deployment path** for the eventual Raspberry Pi 5. It gives the laptop and Pi the same runtime while retaining a deliberately small stack: one FastAPI container and one SQLite file. Direct Python remains the faster option for day-to-day development because it supports reload mode.

With Docker Desktop running on Windows, start the dashboard with:

```powershell
docker compose up --build
```

It is bound to `127.0.0.1:8000` by default, so it remains available only on the machine running it. The SQLite databases are stored outside the container at `data/dashboard.db` and `data/finance.db`; rebuilding or replacing the container does not erase them.

The Compose setup also mounts `C:\work\local\AI\job-hunt-agent\data\job_postings` as a read-only source. On **Job Applications**, use **Import Job-Hunt data** to synchronize the agent's posting status into the dashboard Kanban. The source files are never changed. To use a different source location, set `JOB_POSTINGS_DIR_HOST` before starting Docker.

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
2. Copy the project folder and, if applicable, its `data/dashboard.db` file to the Pi.
3. Before the first start, make the data directory writable by the container user:

   ```bash
   mkdir -p data
   sudo chown -R 10001:10001 data
   ```

4. Start with `docker compose up -d --build` for Pi-local access, or set `DASHBOARD_BIND_ADDRESS=0.0.0.0` for trusted-LAN access.
5. Keep it LAN-only initially; add Tailscale later for remote access.
6. Back up the `data` directory regularly. It is the persistent application state.
7. Optionally self-host Bootstrap, HTMX, and ApexCharts assets so the UI does not depend on CDN access.

If you also move the Job-Hunt Agent to the Pi, set its posting directory before starting the dashboard so the importer can read it:

```bash
export JOB_POSTINGS_DIR_HOST=/home/pi/job-hunt-agent/data/job_postings
docker compose up -d --build
```

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
