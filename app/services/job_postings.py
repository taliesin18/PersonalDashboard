from __future__ import annotations

import json
from pathlib import Path

from ..db import get_connection

SOURCE_NAME = "Job-Hunt Agent"
STATUS_MAP = {
    "application_sent": ("Applied", "Active", "Await response"),
    "initial_interview": ("Recruiter Screen", "Active", "Prepare for initial interview"),
    "rejected": ("Rejected / Closed", "Closed", "No action needed"),
}
DEFAULT_STATUS = ("Applied", "Active", "Review job posting")


def import_job_postings(directory: Path) -> dict[str, int]:
    """Upsert Job-Hunt Agent postings by their stable source ID.

    Source files remain read-only. The agent's workflow status is authoritative
    for imported records; dashboard-only fields such as follow-up dates remain.
    """
    result = {"scanned": 0, "created": 0, "updated": 0, "skipped": 0}

    with get_connection() as conn:
        for path in sorted(directory.glob("*.json")):
            if path.name == "example_job.json":
                continue
            result["scanned"] += 1
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                result["skipped"] += 1
                continue

            external_id = str(record.get("id") or "").strip()
            company = str(record.get("company") or "").strip()
            role = str(record.get("title") or "").strip()
            if not external_id or not company or not role:
                result["skipped"] += 1
                continue

            stage, status, default_action = STATUS_MAP.get(
                str(record.get("status") or "").strip().lower(), DEFAULT_STATUS
            )
            application_date = str(record.get("date_saved") or "").strip()
            job_url = str(record.get("url") or "").strip()
            existing = conn.execute(
                "SELECT id, stage FROM job_applications WHERE external_id = ?", (external_id,)
            ).fetchone()

            if existing:
                stage_changed = existing["stage"] != stage
                conn.execute(
                    """
                    UPDATE job_applications
                    SET company = ?, role = ?, stage = ?, application_date = ?, job_url = ?,
                        source = ?, status = ?,
                        stage_changed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE stage_changed_at END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        company,
                        role,
                        stage,
                        application_date,
                        job_url,
                        SOURCE_NAME,
                        status,
                        stage_changed,
                        existing["id"],
                    ),
                )
                result["updated"] += 1
            else:
                conn.execute(
                    """
                    INSERT INTO job_applications (
                        company, role, stage, application_date, work_setup, next_action,
                        source, external_id, job_url, status
                    ) VALUES (?, ?, ?, ?, 'TBD', ?, ?, ?, ?, ?)
                    """,
                    (
                        company,
                        role,
                        stage,
                        application_date,
                        default_action,
                        SOURCE_NAME,
                        external_id,
                        job_url,
                        status,
                    ),
                )
                result["created"] += 1

    return result
