from __future__ import annotations

import calendar
import os
import platform
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlparse

import psutil
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .db import execute, fetch_all, fetch_one, init_db
from .finance_db import (
    finance_execute,
    finance_fetch_all,
    finance_fetch_one,
    init_finance_db,
)
from .services.job_postings import import_job_postings

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
FINANCIAL_ACCOUNT_TYPES = ("Bank", "Investment", "Cash", "E-Wallet")
FINANCIAL_CURRENCIES = ("PHP", "USD")
DEFAULT_JOB_POSTINGS_DIR = (
    BASE_DIR.parent.parent / "AI" / "job-hunt-agent" / "data" / "job_postings"
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    init_finance_db()


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


def format_money(amount_minor: int, currency: str) -> str:
    amount = Decimal(amount_minor) / Decimal(100)
    symbols = {"PHP": "₱", "USD": "$"}
    prefix = symbols.get(currency, f"{currency} ")
    return f"{prefix}{amount:,.2f}"


def money_to_minor(value: str, *, allow_zero: bool = False) -> int:
    try:
        amount = Decimal(value.strip().replace(",", ""))
    except (InvalidOperation, AttributeError):
        raise HTTPException(status_code=422, detail="Enter a valid monetary amount") from None
    if amount < 0 or (amount == 0 and not allow_zero):
        raise HTTPException(status_code=422, detail="Amount must be greater than zero")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def advance_one_month(value: date) -> date:
    month = value.month + 1
    year = value.year
    if month == 13:
        year += 1
        month = 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def safe_external_url(value: str | None) -> str:
    candidate = (value or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return candidate
    return ""


def job_postings_directory() -> Path:
    configured = os.getenv("JOB_POSTINGS_DIR")
    return Path(configured) if configured else DEFAULT_JOB_POSTINGS_DIR


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
        fetch_all(
            "SELECT * FROM job_applications WHERE status = 'Active' ORDER BY updated_at DESC"
        )
    )


def full_pipeline() -> list[dict]:
    return enrich_jobs(fetch_all("SELECT * FROM job_applications ORDER BY updated_at DESC"))


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
    projects = fetch_all(
        """
        SELECT projects.*, COUNT(project_artifacts.id) AS artifact_count
        FROM projects
        LEFT JOIN project_artifacts ON project_artifacts.project_id = projects.id
        GROUP BY projects.id
        ORDER BY projects.updated_at DESC
        """
    )
    artifacts_by_project: dict[int, list[dict]] = {}
    for artifact in fetch_all(
        "SELECT project_id, label, artifact_type, url FROM project_artifacts ORDER BY created_at DESC, id DESC"
    ):
        artifact["url"] = safe_external_url(artifact["url"])
        if artifact["url"]:
            artifacts_by_project.setdefault(artifact["project_id"], []).append(artifact)

    for project in projects:
        project["repo_url"] = safe_external_url(project["repo"])
        resources = []
        if project["repo_url"]:
            resources.append(
                {
                    "label": "Primary repository / reference",
                    "artifact_type": "Primary",
                    "url": project["repo_url"],
                }
            )
        resources.extend(artifacts_by_project.get(project["id"], []))
        project["resources"] = resources
    return projects


def get_project(project_id: int) -> dict:
    project = fetch_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project["repo_url"] = safe_external_url(project["repo"])
    return project


def get_project_artifacts(project_id: int) -> list[dict]:
    return fetch_all(
        "SELECT * FROM project_artifacts WHERE project_id = ? ORDER BY created_at DESC, id DESC",
        (project_id,),
    )


def learning_register() -> list[dict]:
    tracks = fetch_all(
        """
        SELECT * FROM learning_items
        ORDER BY CASE status WHEN 'Active' THEN 1 WHEN 'Planned' THEN 2 ELSE 3 END,
                 updated_at DESC
        """
    )
    for track in tracks:
        track["resource_url"] = safe_external_url(track["url"])
    return tracks


def get_learning_item(item_id: int) -> dict:
    item = fetch_one("SELECT * FROM learning_items WHERE id = ?", (item_id,))
    if not item:
        raise HTTPException(status_code=404, detail="Learning item not found")
    item["resource_url"] = safe_external_url(item["url"])
    return item


def financial_accounts() -> list[dict]:
    accounts = finance_fetch_all(
        """
        SELECT financial_accounts.*,
               financial_accounts.opening_balance_minor + COALESCE(SUM(
                   CASE financial_transactions.transaction_type
                       WHEN 'Inflow' THEN financial_transactions.amount_minor
                       WHEN 'Outflow' THEN -financial_transactions.amount_minor
                       ELSE 0
                   END
               ), 0) AS current_balance_minor
        FROM financial_accounts
        LEFT JOIN financial_transactions
            ON financial_transactions.account_id = financial_accounts.id
        GROUP BY financial_accounts.id
        ORDER BY CASE financial_accounts.account_type
                     WHEN 'Bank' THEN 1 WHEN 'E-Wallet' THEN 2 WHEN 'Cash' THEN 3 ELSE 4
                 END, financial_accounts.name
        """
    )
    for account in accounts:
        account["balance_display"] = format_money(
            account["current_balance_minor"], account["currency"]
        )
    return accounts


def financial_context(request: Request) -> dict:
    today = date.today()
    month = today.strftime("%Y-%m")
    accounts = financial_accounts()
    transactions = finance_fetch_all(
        """
        SELECT financial_transactions.*, financial_accounts.name AS account_name,
               financial_accounts.currency
        FROM financial_transactions
        JOIN financial_accounts ON financial_accounts.id = financial_transactions.account_id
        ORDER BY financial_transactions.occurred_on DESC, financial_transactions.id DESC
        LIMIT 15
        """
    )
    for transaction in transactions:
        transaction["amount_display"] = format_money(
            transaction["amount_minor"], transaction["currency"]
        )
        transaction["type_class"] = (
            "text-success" if transaction["transaction_type"] == "Inflow" else "text-danger"
        )

    monthly_totals = finance_fetch_one(
        """
        SELECT
            COALESCE(SUM(CASE WHEN financial_transactions.transaction_type = 'Inflow'
                              THEN financial_transactions.amount_minor ELSE 0 END), 0) AS inflow_minor,
            COALESCE(SUM(CASE WHEN financial_transactions.transaction_type = 'Outflow'
                              THEN financial_transactions.amount_minor ELSE 0 END), 0) AS outflow_minor
        FROM financial_transactions
        JOIN financial_accounts ON financial_accounts.id = financial_transactions.account_id
        WHERE substr(financial_transactions.occurred_on, 1, 7) = ?
          AND financial_accounts.currency = 'PHP'
        """,
        (month,),
    ) or {"inflow_minor": 0, "outflow_minor": 0}

    recurring = finance_fetch_all(
        """
        SELECT recurring_payments.*, financial_accounts.name AS account_name,
               financial_accounts.currency
        FROM recurring_payments
        JOIN financial_accounts ON financial_accounts.id = recurring_payments.account_id
        WHERE recurring_payments.active = 1
        ORDER BY recurring_payments.next_due_date, recurring_payments.name
        """
    )
    for payment in recurring:
        due = parse_date(payment["next_due_date"])
        payment["amount_display"] = format_money(payment["amount_minor"], payment["currency"])
        payment["due_display"] = format_date(payment["next_due_date"])
        payment["due_state"] = (
            "overdue" if due and due < today
            else "today" if due == today
            else "scheduled"
        )

    php_cash_minor = sum(
        account["current_balance_minor"]
        for account in accounts
        if account["currency"] == "PHP" and account["account_type"] != "Investment"
    )
    php_investment_minor = sum(
        account["current_balance_minor"]
        for account in accounts
        if account["currency"] == "PHP" and account["account_type"] == "Investment"
    )
    monthly_payment_minor = sum(
        payment["amount_minor"] for payment in recurring if payment["currency"] == "PHP"
    )

    return {
        "request": request,
        "page": "financials",
        "accounts": accounts,
        "transactions": transactions,
        "recurring": recurring,
        "account_types": FINANCIAL_ACCOUNT_TYPES,
        "currencies": FINANCIAL_CURRENCIES,
        "today": today.isoformat(),
        "summary": {
            "cash_display": format_money(php_cash_minor, "PHP"),
            "investment_display": format_money(php_investment_minor, "PHP"),
            "inflow_display": format_money(monthly_totals["inflow_minor"], "PHP"),
            "outflow_display": format_money(monthly_totals["outflow_minor"], "PHP"),
            "monthly_payment_display": format_money(monthly_payment_minor, "PHP"),
        },
    }


def get_financial_account(account_id: int) -> dict:
    account = finance_fetch_one("SELECT * FROM financial_accounts WHERE id = ?", (account_id,))
    if not account:
        raise HTTPException(status_code=404, detail="Financial account not found")
    return account


def dashboard_context(request: Request) -> dict:
    projects = fetch_all("SELECT * FROM projects ORDER BY priority = 'High' DESC, updated_at DESC")
    jobs = active_pipeline()
    priorities = fetch_all("SELECT * FROM priorities WHERE done = 0 ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, created_at")
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
    }


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", dashboard_context(request))


@app.get("/projects", response_class=HTMLResponse)
def projects_page(request: Request):
    projects = project_register()
    return templates.TemplateResponse(
        "projects.html",
        {"request": request, "page": "projects", "projects": projects},
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
    execute(
        """
        INSERT INTO projects (name, status, priority, progress, next_task, repo)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name.strip(), status, priority, max(0, min(progress, 100)), next_task.strip(), repo.strip()),
    )
    if request.headers.get("HX-Request") == "true":
        projects = project_register()
        return templates.TemplateResponse(
            "partials/project_rows.html",
            {"request": request, "projects": projects},
        )
    return RedirectResponse("/projects", status_code=303)


@app.get("/projects/{project_id}/edit", response_class=HTMLResponse)
def edit_project_page(project_id: int, request: Request):
    return templates.TemplateResponse(
        "project_edit.html",
        {
            "request": request,
            "page": "projects",
            "project": get_project(project_id),
            "artifacts": get_project_artifacts(project_id),
        },
    )


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
    get_project(project_id)
    execute(
        """
        UPDATE projects
        SET name = ?, status = ?, priority = ?, progress = ?, next_task = ?, repo = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            name.strip(),
            status,
            priority,
            max(0, min(progress, 100)),
            next_task.strip(),
            repo.strip(),
            project_id,
        ),
    )
    return RedirectResponse(f"/projects/{project_id}/edit", status_code=303)


@app.post("/projects/{project_id}/artifacts")
def add_project_artifact(
    project_id: int,
    request: Request,
    label: str = Form(...),
    artifact_type: str = Form("Link"),
    url: str = Form(...),
):
    get_project(project_id)
    safe_url = safe_external_url(url)
    if not safe_url:
        raise HTTPException(status_code=422, detail="Artifact links must start with http:// or https://")
    execute(
        """
        INSERT INTO project_artifacts (project_id, label, artifact_type, url)
        VALUES (?, ?, ?, ?)
        """,
        (project_id, label.strip(), artifact_type, safe_url),
    )
    artifacts = get_project_artifacts(project_id)
    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(
            "partials/project_artifacts.html",
            {"request": request, "artifacts": artifacts},
        )
    return RedirectResponse(f"/projects/{project_id}/edit", status_code=303)


@app.post("/artifacts/{artifact_id}/delete")
def delete_project_artifact(artifact_id: int, request: Request):
    artifact = fetch_one("SELECT * FROM project_artifacts WHERE id = ?", (artifact_id,))
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    execute("DELETE FROM project_artifacts WHERE id = ?", (artifact_id,))
    artifacts = get_project_artifacts(artifact["project_id"])
    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(
            "partials/project_artifacts.html",
            {"request": request, "artifacts": artifacts},
        )
    return RedirectResponse(f"/projects/{artifact['project_id']}/edit", status_code=303)


@app.get("/learning", response_class=HTMLResponse)
def learning_page(request: Request):
    return templates.TemplateResponse(
        "learning.html",
        {"request": request, "page": "learning", "tracks": learning_register()},
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
    resource_url = safe_external_url(url)
    if url.strip() and not resource_url:
        raise HTTPException(status_code=422, detail="Learning links must start with http:// or https://")
    progress_value = int(progress) if progress.isdigit() else None
    if progress_value is not None and not 0 <= progress_value <= 100:
        raise HTTPException(status_code=422, detail="Progress must be between 0 and 100")
    execute(
        """
        INSERT INTO learning_items
        (title, provider, url, status, progress, current_topic, next_action)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title.strip(),
            provider.strip(),
            resource_url,
            status,
            progress_value,
            current_topic.strip(),
            next_action.strip(),
        ),
    )
    return RedirectResponse("/learning", status_code=303)


@app.get("/learning/{item_id}/edit", response_class=HTMLResponse)
def edit_learning_page(item_id: int, request: Request):
    return templates.TemplateResponse(
        "learning_edit.html",
        {"request": request, "page": "learning", "track": get_learning_item(item_id)},
    )


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
    get_learning_item(item_id)
    resource_url = safe_external_url(url)
    if url.strip() and not resource_url:
        raise HTTPException(status_code=422, detail="Learning links must start with http:// or https://")
    progress_value = int(progress) if progress.isdigit() else None
    if progress_value is not None and not 0 <= progress_value <= 100:
        raise HTTPException(status_code=422, detail="Progress must be between 0 and 100")
    execute(
        """
        UPDATE learning_items
        SET title = ?, provider = ?, url = ?, status = ?, progress = ?, current_topic = ?,
            next_action = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            title.strip(),
            provider.strip(),
            resource_url,
            status,
            progress_value,
            current_topic.strip(),
            next_action.strip(),
            item_id,
        ),
    )
    return RedirectResponse("/learning", status_code=303)


@app.get("/financials", response_class=HTMLResponse)
def financials_page(request: Request):
    return templates.TemplateResponse("financials.html", financial_context(request))


@app.post("/financials/accounts")
def add_financial_account(
    name: str = Form(...),
    institution: str = Form(""),
    account_type: str = Form("Bank"),
    currency: str = Form("PHP"),
    opening_balance: str = Form("0"),
):
    if account_type not in FINANCIAL_ACCOUNT_TYPES:
        raise HTTPException(status_code=422, detail="Unknown account type")
    if currency not in FINANCIAL_CURRENCIES:
        raise HTTPException(status_code=422, detail="Unknown currency")
    finance_execute(
        """
        INSERT INTO financial_accounts
        (name, institution, account_type, currency, opening_balance_minor)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            name.strip(),
            institution.strip(),
            account_type,
            currency,
            money_to_minor(opening_balance, allow_zero=True),
        ),
    )
    return RedirectResponse("/financials", status_code=303)


@app.post("/financials/transactions")
def add_financial_transaction(
    account_id: int = Form(...),
    transaction_type: str = Form(...),
    amount: str = Form(...),
    occurred_on: str = Form(...),
    category: str = Form(""),
    description: str = Form(""),
):
    if transaction_type not in {"Inflow", "Outflow"}:
        raise HTTPException(status_code=422, detail="Transaction type must be Inflow or Outflow")
    get_financial_account(account_id)
    if not parse_date(occurred_on):
        raise HTTPException(status_code=422, detail="Enter a valid transaction date")
    finance_execute(
        """
        INSERT INTO financial_transactions
        (account_id, occurred_on, transaction_type, category, description, amount_minor)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            account_id,
            occurred_on,
            transaction_type,
            category.strip(),
            description.strip(),
            money_to_minor(amount),
        ),
    )
    return RedirectResponse("/financials", status_code=303)


@app.post("/financials/recurring-payments")
def add_recurring_payment(
    account_id: int = Form(...),
    name: str = Form(...),
    amount: str = Form(...),
    next_due_date: str = Form(...),
    category: str = Form("Monthly payment"),
):
    get_financial_account(account_id)
    if not parse_date(next_due_date):
        raise HTTPException(status_code=422, detail="Enter a valid due date")
    finance_execute(
        """
        INSERT INTO recurring_payments
        (account_id, name, category, amount_minor, next_due_date)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            account_id,
            name.strip(),
            category.strip(),
            money_to_minor(amount),
            next_due_date,
        ),
    )
    return RedirectResponse("/financials", status_code=303)


@app.post("/financials/recurring-payments/{payment_id}/record")
def record_recurring_payment(payment_id: int):
    payment = finance_fetch_one(
        "SELECT * FROM recurring_payments WHERE id = ? AND active = 1", (payment_id,)
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Monthly payment not found")
    due_date = parse_date(payment["next_due_date"])
    if not due_date:
        raise HTTPException(status_code=422, detail="Monthly payment has an invalid due date")
    finance_execute(
        """
        INSERT INTO financial_transactions
        (account_id, occurred_on, transaction_type, category, description, amount_minor)
        VALUES (?, ?, 'Outflow', ?, ?, ?)
        """,
        (
            payment["account_id"],
            due_date.isoformat(),
            payment["category"],
            f"Monthly payment: {payment['name']}",
            payment["amount_minor"],
        ),
    )
    finance_execute(
        "UPDATE recurring_payments SET next_due_date = ? WHERE id = ?",
        (advance_one_month(due_date).isoformat(), payment_id),
    )
    return RedirectResponse("/financials", status_code=303)


@app.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request):
    view = "kanban" if request.query_params.get("view") == "kanban" else "list"
    jobs = enrich_jobs(fetch_all("SELECT * FROM job_applications ORDER BY updated_at DESC"))
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
            "job_postings_available": job_postings_directory().is_dir(),
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
    if stage not in PIPELINE_STAGES:
        raise HTTPException(status_code=422, detail="Unknown pipeline stage")
    execute(
        """
        INSERT INTO job_applications
        (company, role, stage, application_date, work_setup, salary_text, last_contact,
         next_follow_up, next_action, source, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company.strip(),
            role.strip(),
            stage,
            application_date if parse_date(application_date) else date.today().isoformat(),
            work_setup,
            salary_text.strip(),
            last_contact.strip(),
            next_follow_up if parse_date(next_follow_up) else "",
            next_action.strip(),
            source.strip(),
            "Closed" if stage in CLOSED_STAGES else "Active",
        ),
    )
    if request.headers.get("HX-Request") == "true":
        jobs = full_pipeline()
        if view == "kanban":
            return templates.TemplateResponse(
                "partials/kanban_board.html",
                {
                    "request": request,
                    "stages": PIPELINE_STAGES,
                    "kanban": kanban_groups(jobs),
                },
            )
        return templates.TemplateResponse(
            "partials/job_rows.html",
            {"request": request, "jobs": jobs},
        )
    return RedirectResponse("/jobs?view=kanban" if view == "kanban" else "/jobs", status_code=303)


@app.post("/jobs/import")
def import_jobs_from_agent(view: str = Form("list")):
    directory = job_postings_directory()
    if not directory.is_dir():
        raise HTTPException(status_code=503, detail="Job-Hunt Agent posting directory is not available")
    result = import_job_postings(directory)
    selected_view = "kanban" if view == "kanban" else "list"
    return RedirectResponse(
        f"/jobs?view={selected_view}&imported={result['created']}&updated={result['updated']}",
        status_code=303,
    )


@app.get("/kanban", response_class=HTMLResponse)
def kanban_page(request: Request):
    return RedirectResponse("/jobs?view=kanban", status_code=303)


@app.post("/jobs/{job_id}/stage")
def update_job_stage(job_id: int, request: Request, stage: str = Form(...)):
    if stage not in PIPELINE_STAGES:
        raise HTTPException(status_code=422, detail="Unknown pipeline stage")
    execute(
        """
        UPDATE job_applications
        SET stage = ?, status = ?, stage_changed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (stage, "Closed" if stage in CLOSED_STAGES else "Active", job_id),
    )
    if request.headers.get("HX-Request") == "true":
        jobs = full_pipeline()
        return templates.TemplateResponse(
            "partials/kanban_board.html",
            {
                "request": request,
                "stages": PIPELINE_STAGES,
                "kanban": kanban_groups(jobs),
            },
        )
    return RedirectResponse("/jobs?view=kanban", status_code=303)


@app.post("/priorities/{priority_id}/toggle")
def toggle_priority(priority_id: int, request: Request):
    execute("UPDATE priorities SET done = CASE done WHEN 0 THEN 1 ELSE 0 END WHERE id = ?", (priority_id,))
    if request.headers.get("HX-Request") == "true":
        priorities = fetch_all("SELECT * FROM priorities WHERE done = 0 ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, created_at")
        return templates.TemplateResponse(
            "partials/priorities.html",
            {"request": request, "priorities": priorities[:6]},
        )
    return RedirectResponse("/", status_code=303)


@app.get("/health")
def health():
    return {"status": "ok", "service": "personal-engineering-dashboard"}
