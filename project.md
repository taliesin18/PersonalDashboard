# AI Dashboard — Project Context

## 1. Project Summary

This project is a **Personal Engineering Dashboard** intended to become a central command center for:

- Current software and side projects
- Ongoing job applications
- Interview and follow-up tracking
- Learning and certification progress
- Daily priorities / attention queue
- Local machine and future Raspberry Pi observability
- Future AI / automation integrations

The project will be developed first on a Windows laptop, then migrated later to a **Raspberry Pi 5** for 24/7 home hosting.

The dashboard should remain lightweight, easy to maintain, mobile-ready, and suitable for eventual Raspberry Pi deployment.

---

## 2. Current Development Location

Primary local project path:

```text
C:\work\local\ai-dashboard
```

Future shared-data location may use:

```text
C:\work\local\shared_data
```

Potential shared SQLite database:

```text
C:\work\local\shared_data\careerhub.db
```

---

## 3. Core Goals

The dashboard should answer:

> "What needs my attention today?"

It should provide one place to observe:

- What projects are active
- Which tasks are blocked or overdue
- Which job applications are still active
- Which applications need follow-up
- Upcoming interviews
- Certification / learning progress
- Laptop / Raspberry Pi system health
- Future automation and agent status

---

## 4. Agreed Technology Stack

Keep the stack deliberately lightweight.

### Backend

- Python
- FastAPI

### Frontend

- Jinja2
- HTMX
- Bootstrap 5
- Custom CSS

### Database

- SQLite

### System Observability

- psutil

### Charts

Preferred:

- ApexCharts

Alternative:

- Chart.js

ApexCharts is preferred because the dashboard should visually resemble a modern dark admin dashboard.

### Explicitly Avoid for MVP

Do not introduce unless there is a strong future requirement:

- React
- Angular
- Vue
- Node.js frontend build pipeline
- PostgreSQL
- Redis
- Kubernetes
- Grafana
- Prometheus
- large JS frameworks
- heavy container stacks

Docker may be introduced later if useful, but is not required for the first version.

---

## 5. Design Direction

The UI should be inspired by the supplied dark admin dashboard reference image.

The goal is to mimic the **overall layout and visual language**, not reproduce proprietary branding.

### Visual Style

- Dark navy / purple background
- Fixed left sidebar on desktop
- Top header
- Rounded metric cards
- Soft shadows
- Accent colors for states and KPIs
- Compact data presentation
- Modern admin-dashboard aesthetic
- Large chart area
- Lower panels for tables / kanban / analytics

### Desktop First

The first version should prioritize desktop screens.

Typical layout:

```text
+-------------------------------------------------------------+
| Sidebar | Header                                            |
|         +---------------------------------------------------+
|         | Summary Cards                                     |
|         +---------------------------------------------------+
|         | Main Analytics Chart                              |
|         +---------------------------------------------------+
|         | Job / Project panels                              |
|         +---------------------------------------------------+
```

### Mobile Ready

Even though desktop is first priority, all UI decisions must support future phone usage.

Use:

- Bootstrap responsive grid
- mobile offcanvas sidebar
- stacked cards on small screens
- horizontally scrollable Kanban where necessary
- touch-friendly buttons
- responsive chart widths
- readable typography

The dashboard may later become a PWA so it can be added to an Android home screen without creating a dedicated Android APK.

---

## 6. Current MVP Scope

The existing MVP concept includes:

### Dashboard / Overview

- Active Projects
- Ongoing Job Applications
- Today's Priorities
- System Health
- Follow-up alerts
- Upcoming interviews
- Recent activity

### Projects

Track:

- Project name
- Status
- Priority
- Progress percentage
- Next task
- Repository / reference
- Milestones
- Blockers
- Recent activity

Example active projects may include:

- PBMS
- Local RAG Job-Hunt Agent
- Local AI Coding Assistant
- DevOps / AWS labs
- IoT / hydroponics prototypes
- Robotics / AI training business ideas

### Job Applications

Track:

- Company
- Role
- Application date
- Current stage
- Recruiter
- Salary range / asking salary
- Work setup
- Source
- Resume version used
- Last contact
- Follow-up date
- Next action
- Notes
- Job description reference

### Attention Queue

Aggregate actions from different modules.

Examples:

- Follow up with recruiter
- Prepare for technical interview
- Complete project task
- Finish certification lab
- Review Japanese study item

HTMX can be used to mark tasks complete without reloading the entire page.

### System Health

Current laptop first, Raspberry Pi later.

Show:

- CPU usage
- RAM usage
- Disk usage
- Hostname
- OS
- Uptime
- application health

Potential future items:

- CPU temperature
- service health
- Docker container state
- network state
- backup state
- disk I/O
- application logs

---

## 7. Main Dashboard Layout

Suggested sidebar:

```text
Dashboard
Projects
Job Applications
Kanban
Learning
Observability
Automations
Settings
```

Suggested top summary cards:

```text
Active Projects
Applications
Upcoming Interviews
Pending Follow-ups
Study Progress
System Status
```

Suggested main page:

```text
Dashboard
├── Summary KPI cards
├── Job application trend chart
├── Project activity / productivity chart
├── Job Application Kanban preview
├── Today's Attention Queue
├── Recent Activity
└── System Health
```

---

## 8. Job Application Kanban

The dashboard should include a Job Application Kanban.

Recommended stages:

```text
Applied
Recruiter Screen
Assessment / Exam
Technical Interview
Final Interview
Offer
Accepted
Rejected / Closed
```

Cards should eventually support:

- Company
- Role
- Application date
- Days in current stage
- Last contact
- Next follow-up
- Work setup
- Salary
- Notes
- Match score if available

Future enhancement:

- drag-and-drop stage updates
- aging indicators
- overdue follow-up highlighting
- filters by role / company / status / salary / work setup
- search

---

## 9. Shared Data Strategy

The dashboard should ideally reference the **same job data** used by the Job-Hunt Agent.

The objective is to avoid maintaining duplicate copies of job application information.

### Recommended Approach

Use a **shared SQLite database** as the single source of truth.

Example:

```text
C:\work\local\shared_data\careerhub.db
```

Both:

- AI Dashboard
- Job-Hunt Agent

should read and write to the same database.

### Why SQLite

SQLite is preferred because it is:

- lightweight
- serverless
- easy to back up
- easy to migrate to Raspberry Pi
- suitable for a personal single-user application
- better for structured querying than many JSON files
- simple to use with FastAPI

### Possible Schema

Initial tables:

```text
applications
application_events
job_postings
projects
project_tasks
learning_items
attention_items
system_events
```

### JSON Compatibility

The Job-Hunt Agent may continue to store raw source data in:

```text
job-hunt-agent\data\
```

A lightweight importer can:

1. scan JSON files
2. normalize records
3. insert or update SQLite
4. let the dashboard read from SQLite

This prevents tight long-term coupling to raw JSON files.

---

## 10. Data Synchronization Options

### Option A — Read JSON on Page Load

Simplest MVP.

Good for:

- read-heavy usage
- small data set

Weakness:

- multiple writers can become messy

### Option B — HTMX Polling

Recommended lightweight refresh behavior.

Example:

- refresh Kanban every 10–30 seconds
- reload only the relevant partial

### Option C — Python File Watcher

Use `watchdog` later if desired.

When an agent JSON file changes:

- detect change
- import to SQLite
- dashboard sees updated data

### Preferred Long-Term Strategy

Shared SQLite database with optional JSON import.

---

## 11. Suggested Local Folder Structure

```text
C:\work\local\
│
├── ai-dashboard\
│   ├── app\
│   │   ├── main.py
│   │   ├── routes\
│   │   ├── services\
│   │   ├── models\
│   │   └── db\
│   │
│   ├── templates\
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── projects.html
│   │   ├── applications.html
│   │   ├── kanban.html
│   │   └── partials\
│   │
│   ├── static\
│   │   ├── css\
│   │   ├── js\
│   │   └── img\
│   │
│   ├── data\
│   ├── tests\
│   ├── requirements.txt
│   ├── README.md
│   └── project.md
│
├── job-hunt-agent\
│   ├── data\
│   ├── src\
│   └── ...
│
└── shared_data\
    └── careerhub.db
```

Exact structure can evolve as implementation grows.

---

## 12. FastAPI Application Principles

Keep the backend modular but simple.

Suggested responsibilities:

```text
app/main.py
    FastAPI application setup

routes/
    page and API routes

services/
    reusable business logic

models/
    application / project / task models

db/
    SQLite connection and queries
```

The application should expose a basic health endpoint:

```text
GET /health
```

Example response:

```json
{
  "status": "ok"
}
```

---

## 13. Frontend Principles

Prefer server-rendered HTML.

Use Jinja for:

- page layout
- initial data rendering
- reusable partials

Use HTMX for:

- refreshing sections
- marking tasks complete
- filtering tables
- updating Kanban states
- modal / inline forms
- periodic refreshes

Use Bootstrap for:

- responsive layout
- cards
- navbar / sidebar
- offcanvas mobile menu
- forms
- badges
- tables

Use custom CSS for the dark dashboard design.

---

## 14. Analytics Ideas

Potential charts:

### Job Applications

- applications per week
- responses per week
- interview count
- conversion by pipeline stage
- average days per stage
- source distribution
- remote vs hybrid vs onsite
- salary distribution
- role category performance

### Projects

- tasks completed per week
- project completion %
- active vs blocked
- milestone progress
- recent Git activity

### Learning

- study sessions per week
- certification completion %
- labs completed
- study streak

---

## 15. Learning / Certification Module

Potential tracks:

```text
AWS Solutions Architect Associate
Linux / DevOps
Docker
Kubernetes
Terraform
Microsoft IAM / Entra
AI / Agentic Workflows
Japanese N2
```

Track:

- current topic
- percentage complete
- completed labs
- next activity
- target exam
- notes

---

## 16. Future AI / Automation Integration

The dashboard may eventually become a front end for local AI and automation tools.

Potential integrations:

- Ollama
- local coding assistant
- Job-Hunt RAG Agent
- n8n
- GitHub
- calendar
- email
- MCP-enabled tools

Potential AI prompts:

```text
What should I work on tonight?

Which job applications need follow-up?

Which active project has the highest priority?

Summarize my progress this week.

Show applications with no recruiter activity for more than 7 days.
```

Potential future architecture:

```text
Dashboard
   |
   +-- Projects DB
   +-- Job Applications DB
   +-- Learning DB
   +-- GitHub
   +-- Calendar
   +-- Automation Engine
   +-- Ollama / AI Assistant
```

---

## 17. Raspberry Pi Migration Target

Target hardware:

- Raspberry Pi 5
- initially 16 GB microSD
- future storage upgrade recommended

### Migration Philosophy

The laptop version should use the same codebase that later runs on Raspberry Pi OS.

Avoid Windows-specific application logic.

Expected migration:

```text
Windows Laptop
      |
      | same source code
      v
Raspberry Pi 5
```

Because `psutil` is cross-platform, system-health code should automatically report Linux / Raspberry Pi metrics after migration.

Docker Compose is an appropriate optional deployment layer for the Pi: it preserves the same application runtime across laptop and ARM64 Pi deployments while keeping SQLite as a bind-mounted, easily backed-up file. Keep direct Python/Uvicorn available for quick local development.

---

## 18. Raspberry Pi Storage Considerations

The current 16 GB microSD is acceptable for an MVP but should not be considered the long-term storage solution.

Preferred later upgrade:

- 64–128 GB high-endurance microSD

or preferably:

- USB SSD
- NVMe SSD

The dashboard should therefore avoid unnecessarily large dependencies and local caches.

---

## 19. Raspberry Pi 24/7 Hosting

The Raspberry Pi is intended to run continuously.

Expected average dashboard workload is light.

Important future considerations:

- active cooling
- log rotation
- controlled backups
- clean shutdown
- optional UPS / UPS HAT
- storage health
- systemd service

---

## 20. Network / Security Strategy

The dashboard should **not be publicly exposed directly to the internet**.

### Initial Deployment

LAN only.

Example:

```text
Android / Laptop
      |
   Home Wi-Fi
      |
Raspberry Pi
```

Avoid router port forwarding.

### Remote Access Later

Use Tailscale.

Expected setup:

```text
Android ----\
Laptop ------ Tailscale ---- Raspberry Pi
Desktop ----/
```

### Security Baseline

Future Pi deployment should include:

- no public router port forwarding
- SSH keys
- disable unnecessary password login
- firewall
- non-default user
- automatic security updates
- dashboard authentication
- database not directly exposed
- backups
- log rotation
- Tailscale restricted to trusted devices

---

## 21. Android Strategy

Do not build a native Android app for the first version.

Preferred path:

1. responsive web dashboard
2. optimize for touch
3. add PWA manifest
4. add service worker
5. "Add to Home Screen" on Android

This keeps one codebase for:

- desktop
- laptop
- Android
- Raspberry Pi hosting

---

## 22. Local Development Security

During normal Windows development:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

This is local-machine only.

For temporary phone testing on a trusted Wi-Fi network:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Only allow private-network access through Windows Firewall.

Do not expose this directly to the public internet.

---

## 23. Development Priorities

### Phase 1 — UI / Foundation

- dark dashboard redesign
- fixed desktop sidebar
- mobile offcanvas sidebar
- summary cards
- dashboard charts
- project cards
- application cards
- system-health panel
- responsive layout

### Phase 2 — Job Application System

- shared SQLite schema
- application list
- Kanban
- stage aging
- next action
- follow-up date
- filters
- application notes
- job source tracking

### Phase 3 — Shared Agent Data

- integrate Job-Hunt Agent
- JSON import if necessary
- migrate to shared SQLite
- eliminate duplicate job records
- HTMX refresh

### Phase 4 — Project Management

- milestones
- tasks
- blockers
- recent activity
- GitHub integration
- progress analytics

### Phase 5 — Learning

- certifications
- labs
- study progress
- study streak
- target dates

### Phase 6 — Mobile / PWA

- mobile layout polish
- touch interactions
- PWA manifest
- service worker
- home-screen install

### Phase 7 — Raspberry Pi

- copy application
- move database
- install Docker Engine and Compose plugin
- configure Docker Compose restart policy, or a small systemd unit only if Docker is not used
- add cooling / storage monitoring
- LAN hosting
- Tailscale

### Phase 8 — Automation / AI

- n8n
- Ollama
- AI assistant
- Job-Hunt Agent
- automated reminders
- project intelligence
- dashboard natural-language queries

---

## 24. Immediate Next Implementation Target

### Completed foundation

The initial visual redesign and job-workflow foundation are now implemented:

- dark, desktop-first dashboard shell with responsive mobile navigation
- SQLite-backed projects, priorities, and job applications
- overview KPIs, live machine health, pipeline stage chart, and follow-up watchlist
- application date, follow-up date, source, and stage-change tracking
- job Kanban with stage aging and HTMX stage updates
- safe migration of early MVP job records to the standardized pipeline labels
- editable project portfolio entries with linked GitHub, Google Drive, demo, and document artifacts
- read-only, idempotent import from the local Job-Hunt Agent posting folder
- editable Learning module seeded with SC-900, LabEx DevOps, and AWS SAA study tracks
- local-only Financials module with a separate SQLite database for banks, investments, inflow/outflow history, and recurring monthly payments
- hotfix refactor: projects, job applications, learning items, and priorities now use the Personal Data Layer API instead of the dashboard database or Job-Hunt file mount; the current snapshot is deliberately read-only
- Homelab local-services view uses a separate, read-only Host Observer API that normalizes host metrics and listening TCP services across Windows, Linux, and Raspberry Pi OS

### Recommended next implementation target

Connect the dashboard to the Job-Hunt Agent's data without duplicating records.

### UI

Refine job management with edit/delete controls, overdue follow-up indicators, and optional filters.

### Data

Implement a small, idempotent importer for the Job-Hunt Agent's JSON records, then move both applications toward the planned shared SQLite database.

---

## 25. Project Philosophy

When making implementation decisions, prioritize:

1. Lightweight
2. Maintainable
3. Raspberry Pi compatible
4. Mobile ready
5. Local first
6. Secure by default
7. One source of truth
8. Minimal duplicated data
9. Simple deployment
10. Incremental evolution over premature complexity

The project should remain useful even if no AI component is running.

AI and automation should enhance the dashboard rather than become hard dependencies.

---

## 26. Context for Future Coding Agents

When modifying this project:

- Preserve FastAPI + Python.
- Preserve Jinja2 + HTMX + Bootstrap unless there is a strong reason to change.
- Do not replace the frontend with React.
- Keep Raspberry Pi 5 compatibility in mind.
- Optimize the first UI for desktop.
- Always preserve responsive mobile behavior.
- Prefer SQLite for local structured persistence.
- Prefer shared data rather than duplicated application records.
- Do not directly expose the dashboard to the public internet.
- Keep dependencies small.
- Prefer progressive enhancement.
- Use the dark admin-dashboard visual direction already agreed upon.
- Treat the dashboard as a personal command center rather than a generic CRUD application.
