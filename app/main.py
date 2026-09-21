from __future__ import annotations

import platform
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import psutil
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .services.personal_data import PersonalDataLayerUnavailable, get_records
from .services.host_observer import HostObserverUnavailable, get_snapshot

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Personal Engineering Dashboard", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

PIPELINE_STAGES = (
    "Applied",
    "Recruiter Screen",
    "Assessment / Exam",
    "Technical Interview",
    "Final Interview",
    "Offer",
    "Accepted",
    "Rejected / Closed",
)
CLOSED_STAGES = {"Accepted", "Rejected / Closed"}


@app.on_event("startup")
def startup() -> None:
    """The dashboard is a client; shared records belong to the data-layer API."""


@app.exception_handler(PersonalDataLayerUnavailable)
def personal_data_layer_unavailable(request: Request, error: PersonalDataLayerUnavailable):
    return templates.TemplateResponse(
        "data_layer_unavailable.html",
        {
            "request": request,
            "page": "dashboard",
            "title": "Shared data unavailable",
            "heading": "The Personal Data Layer is not reachable",
            "message": str(error),
            "setup_hint": "Run the Personal Data Layer API on port 8100, then refresh this page.",
        },
        status_code=503,
    )


def homelab_context(request: Request) -> dict:
    try:
        snapshot = get_snapshot()
        return {
            "request": request,
            "page": "homelab",
            "snapshot": snapshot,
            "observer_error": "",
        }
    except HostObserverUnavailable as error:
        return {
            "request": request,
            "page": "homelab",
            "snapshot": None,
            "observer_error": str(error),
        }


def shared_write_not_available() -> None:
    raise HTTPException(
        status_code=409,
        detail=(
            "This shared-data snapshot is read-only. Editing will return when the Personal "
            "Data Layer provides its authenticated write API."
        ),
    )


def system_metrics() -> dict:
    # System users inside minimal containers may have a non-existent home path.
    # In that case, report the container's root filesystem instead.
    disk_path = Path.home()
    if not disk_path.exists():
        disk_path = Path("/")
    disk = psutil.disk_usage(str(disk_path))
    return {
        "cpu": round(psutil.cpu_percent(interval=0.05), 1),
        "memory": round(psutil.virtual_memory().percent, 1),
        "disk": round(disk.percent, 1),
        "platform": platform.system(),
        "hostname": platform.node() or "localhost",
    }


def parse_date(value: str) -> date | None:
    """Return an ISO date when present; tolerate legacy free-text records."""
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def format_date(value: str) -> str:
    parsed = parse_date(value)
    return f"{parsed.strftime('%b')} {parsed.day}" if parsed else "—"


def safe_external_url(value: str | None) -> str:
    candidate = (value or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return candidate
    return ""


def enrich_jobs(jobs: list[dict]) -> list[dict]:
    today = date.today()
    enriched: list[dict] = []
    for job in jobs:
        item = dict(job)
        stage_date = parse_date(item.get("stage_changed_at", "")) or parse_date(item.get("updated_at", ""))
        follow_up = parse_date(item.get("next_follow_up", ""))
        item["days_in_stage"] = max((today - stage_date).days, 0) if stage_date else 0
        item["application_date_display"] = format_date(item.get("application_date", ""))
        item["follow_up_display"] = format_date(item.get("next_follow_up", ""))
        item["job_url"] = safe_external_url(item.get("job_url"))
        item["follow_up_state"] = (
            "overdue" if follow_up and follow_up < today
            else "today" if follow_up == today
            else "scheduled" if follow_up
            else "none"
        )
        enriched.append(item)
    return enriched


def active_pipeline() -> list[dict]:
    return enrich_jobs(
        [job for job in get_records("job-applications") if job.get("status") == "Active"]
    )


def full_pipeline() -> list[dict]:
    return enrich_jobs(get_records("job-applications"))


def kanban_groups(jobs: list[dict]) -> dict[str, list[dict]]:
    groups = {stage: [] for stage in PIPELINE_STAGES}
    for job in jobs:
        groups.setdefault(job["stage"], []).append(job)
    return groups


def pipeline_chart_data(jobs: list[dict]) -> list[dict]:
    groups = kanban_groups(jobs)
    return [
        {"stage": stage, "count": len(groups[stage])}
        for stage in PIPELINE_STAGES
        if stage not in CLOSED_STAGES
    ]


def project_register() -> list[dict]:
    projects = get_records("dashboard-projects")
    for project in projects:
        project["id"] = project.get("source_id")
        project["progress"] = max(0, min(int(project.get("progress") or 0), 100))
        project["artifact_count"] = 0
        project["repo_url"] = safe_external_url(project.get("repo"))
        resources = []
        if project["repo_url"]:
            resources.append(
                {
                    "label": "Primary repository / reference",
                    "artifact_type": "Primary",
                    "url": project["repo_url"],
                }
            )
        project["resources"] = resources
    return projects


def learning_register() -> list[dict]:
    tracks = get_records("learning-items")
    for track in tracks:
        track["id"] = track.get("source_id")
        track["resource_url"] = safe_external_url(track.get("url"))
    return tracks


def dashboard_context(request: Request) -> dict:
    projects = project_register()
    jobs = active_pipeline()
    priorities = [item for item in get_records("priorities") if not item.get("done")]
    follow_ups = sorted(
        [job for job in jobs if job["follow_up_state"] != "none"],
        key=lambda job: job["next_follow_up"],
    )

    stats = {
        "projects": len([p for p in projects if p["status"] in {"Active", "Planning", "Research"}]),
        "high_priority_projects": len([p for p in projects if p["priority"] == "High"]),
        "active_jobs": len(jobs),
        "interviews": len([j for j in jobs if "Interview" in j["stage"]]),
        "follow_ups_due": len([j for j in jobs if j["follow_up_state"] in {"overdue", "today"}]),
        "open_priorities": len(priorities),
    }

    return {
        "request": request,
        "page": "dashboard",
        "projects": projects[:4],
        "jobs": jobs[:5],
        "follow_ups": follow_ups[:4],
        "pipeline_chart": pipeline_chart_data(jobs),
        "priorities": priorities[:6],
        "stats": stats,
        "system": system_metrics(),
        "shared_read_only": True,
    }


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", dashboard_context(request))


@app.get("/projects", response_class=HTMLResponse)
def projects_page(request: Request):
    projects = project_register()
    return templates.TemplateResponse(
        "projects.html",
        {
            "request": request,
            "page": "projects",
            "projects": projects,
            "shared_read_only": True,
        },
    )


@app.post("/projects")
def add_project(
    request: Request,
    name: str = Form(...),
    status: str = Form("Active"),
    priority: str = Form("Medium"),
    progress: int = Form(0),
    next_task: str = Form(""),
    repo: str = Form(""),
):
    shared_write_not_available()


@app.get("/projects/{project_id}/edit", response_class=HTMLResponse)
def edit_project_page(project_id: int, request: Request):
    shared_write_not_available()


@app.post("/projects/{project_id}")
def update_project(
    project_id: int,
    name: str = Form(...),
    status: str = Form("Active"),
    priority: str = Form("Medium"),
    progress: int = Form(0),
    next_task: str = Form(""),
    repo: str = Form(""),
):
    shared_write_not_available()


@app.post("/projects/{project_id}/artifacts")
def add_project_artifact(
    project_id: int,
    request: Request,
    label: str = Form(...),
    artifact_type: str = Form("Link"),
    url: str = Form(...),
):
    shared_write_not_available()


@app.post("/artifacts/{artifact_id}/delete")
def delete_project_artifact(artifact_id: int, request: Request):
    shared_write_not_available()


@app.get("/learning", response_class=HTMLResponse)
def learning_page(request: Request):
    return templates.TemplateResponse(
        "learning.html",
        {
            "request": request,
            "page": "learning",
            "tracks": learning_register(),
            "shared_read_only": True,
        },
    )


@app.post("/learning")
def add_learning_item(
    title: str = Form(...),
    provider: str = Form(""),
    url: str = Form(""),
    status: str = Form("Planned"),
    progress: str = Form(""),
    current_topic: str = Form(""),
    next_action: str = Form(""),
):
    shared_write_not_available()


@app.get("/learning/{item_id}/edit", response_class=HTMLResponse)
def edit_learning_page(item_id: int, request: Request):
    shared_write_not_available()


@app.post("/learning/{item_id}")
def update_learning_item(
    item_id: int,
    title: str = Form(...),
    provider: str = Form(""),
    url: str = Form(""),
    status: str = Form("Planned"),
    progress: str = Form(""),
    current_topic: str = Form(""),
    next_action: str = Form(""),
):
    shared_write_not_available()


@app.get("/financials", response_class=HTMLResponse)
def financials_page(request: Request):
    return templates.TemplateResponse(
        "data_layer_unavailable.html",
        {
            "request": request,
            "page": "financials",
            "title": "Financials pending",
            "heading": "Financial data remains protected",
            "message": (
                "Financial records are not exposed by the Personal Data Layer yet. "
                "The dashboard will not open its legacy finance database while that "
                "authorization boundary is being designed."
            ),
            "setup_hint": "Finance will return after a dedicated, authenticated Personal Data Layer API is approved.",
        },
        status_code=503,
    )


@app.get("/homelab", response_class=HTMLResponse)
def homelab_page(request: Request):
    return templates.TemplateResponse("homelab.html", homelab_context(request))


@app.post("/financials/accounts")
def add_financial_account(
    name: str = Form(...),
    institution: str = Form(""),
    account_type: str = Form("Bank"),
    currency: str = Form("PHP"),
    opening_balance: str = Form("0"),
):
    shared_write_not_available()


@app.post("/financials/transactions")
def add_financial_transaction(
    account_id: int = Form(...),
    transaction_type: str = Form(...),
    amount: str = Form(...),
    occurred_on: str = Form(...),
    category: str = Form(""),
    description: str = Form(""),
):
    shared_write_not_available()


@app.post("/financials/recurring-payments")
def add_recurring_payment(
    account_id: int = Form(...),
    name: str = Form(...),
    amount: str = Form(...),
    next_due_date: str = Form(...),
    category: str = Form("Monthly payment"),
):
    shared_write_not_available()


@app.post("/financials/recurring-payments/{payment_id}/record")
def record_recurring_payment(payment_id: int):
    shared_write_not_available()


@app.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request):
    view = "kanban" if request.query_params.get("view") == "kanban" else "list"
    jobs = full_pipeline()
    return templates.TemplateResponse(
        "jobs.html",
        {
            "request": request,
            "page": "jobs",
            "jobs": jobs,
            "view": view,
            "kanban": kanban_groups(jobs),
            "stages": PIPELINE_STAGES,
            "today": date.today().isoformat(),
            "shared_read_only": True,
            "import_result": {
                "created": request.query_params.get("imported"),
                "updated": request.query_params.get("updated"),
            },
        },
    )


@app.post("/jobs")
def add_job(
    request: Request,
    company: str = Form(...),
    role: str = Form(...),
    stage: str = Form("Applied"),
    application_date: str = Form(""),
    work_setup: str = Form("Remote"),
    salary_text: str = Form(""),
    last_contact: str = Form(""),
    next_follow_up: str = Form(""),
    next_action: str = Form(""),
    source: str = Form(""),
    view: str = Form("list"),
):
    shared_write_not_available()


@app.post("/jobs/import")
def import_jobs_from_agent(view: str = Form("list")):
    shared_write_not_available()


@app.get("/kanban", response_class=HTMLResponse)
def kanban_page(request: Request):
    return RedirectResponse("/jobs?view=kanban", status_code=303)


@app.post("/jobs/{job_id}/stage")
def update_job_stage(job_id: int, request: Request, stage: str = Form(...)):
    shared_write_not_available()


@app.post("/priorities/{priority_id}/toggle")
def toggle_priority(priority_id: int, request: Request):
    shared_write_not_available()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "personal-engineering-dashboard",
        "shared_data_mode": "Personal Data Layer API client",
    }
