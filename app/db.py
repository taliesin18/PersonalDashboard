from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DASHBOARD_DB", BASE_DIR / "data" / "dashboard.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Active',
    priority TEXT NOT NULL DEFAULT 'Medium',
    progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
    next_task TEXT NOT NULL DEFAULT '',
    repo TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'Applied',
    application_date TEXT NOT NULL DEFAULT '',
    work_setup TEXT NOT NULL DEFAULT 'Remote',
    salary_text TEXT NOT NULL DEFAULT '',
    last_contact TEXT NOT NULL DEFAULT '',
    next_follow_up TEXT NOT NULL DEFAULT '',
    next_action TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    external_id TEXT,
    job_url TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Active',
    stage_changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_job_applications_status_stage
ON job_applications (status, stage);

CREATE TABLE IF NOT EXISTS project_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    artifact_type TEXT NOT NULL DEFAULT 'Link',
    url TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_project_artifacts_project_id
ON project_artifacts (project_id);

CREATE TABLE IF NOT EXISTS learning_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Planned',
    progress INTEGER CHECK(progress IS NULL OR progress BETWEEN 0 AND 100),
    current_topic TEXT NOT NULL DEFAULT '',
    next_action TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS priorities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'General',
    priority TEXT NOT NULL DEFAULT 'Medium',
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        migrate_job_applications(conn)
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_job_applications_external_id
            ON job_applications (external_id)
            WHERE external_id IS NOT NULL
            """
        )
        seed_data(conn)
        seed_learning_data(conn)


def migrate_job_applications(conn: sqlite3.Connection) -> None:
    """Bring early MVP databases forward without losing a user's records."""
    existing_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(job_applications)").fetchall()
    }
    additions = {
        "application_date": "TEXT NOT NULL DEFAULT ''",
        "next_follow_up": "TEXT NOT NULL DEFAULT ''",
        "source": "TEXT NOT NULL DEFAULT ''",
        "stage_changed_at": "TEXT NOT NULL DEFAULT ''",
        "external_id": "TEXT",
        "job_url": "TEXT NOT NULL DEFAULT ''",
    }
    for column, definition in additions.items():
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE job_applications ADD COLUMN {column} {definition}")

    # The first MVP used a few loose labels. Normalize only those known labels so
    # existing user-created stages are preserved.
    conn.execute(
        """
        UPDATE job_applications
        SET stage = CASE stage
            WHEN 'Application' THEN 'Applied'
            WHEN 'Screening' THEN 'Recruiter Screen'
            WHEN 'Technical Exam' THEN 'Assessment / Exam'
            ELSE stage
        END
        """
    )
    conn.execute(
        """
        UPDATE job_applications
        SET stage_changed_at = updated_at
        WHERE stage_changed_at = ''
        """
    )


def seed_data(conn: sqlite3.Connection) -> None:
    project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    if project_count == 0:
        conn.executemany(
            """
            INSERT INTO projects (name, status, priority, progress, next_task, repo)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("Example API Service", "Active", "High", 72, "Define the next delivery milestone", ""),
                ("Portfolio Refresh", "Planning", "Medium", 30, "Add your first project artifact", ""),
                ("Learning Sandbox", "Research", "Low", 20, "Choose the next topic to explore", ""),
            ],
        )

    jobs_count = conn.execute("SELECT COUNT(*) FROM job_applications").fetchone()[0]
    if jobs_count == 0:
        conn.executemany(
            """
            INSERT INTO job_applications (
                company, role, stage, application_date, work_setup, salary_text,
                last_contact, next_follow_up, next_action, source, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("Example Company", "Software Engineer", "Recruiter Screen", "", "Remote", "", "Initial response received", "", "Prepare your introduction", "", "Active"),
                ("Sample Organization", "Infrastructure Engineer", "Applied", "", "Hybrid", "", "Application submitted", "", "Set a follow-up reminder", "", "Active"),
            ],
        )

    priorities_count = conn.execute("SELECT COUNT(*) FROM priorities").fetchone()[0]
    if priorities_count == 0:
        conn.executemany(
            "INSERT INTO priorities (title, category, priority, done) VALUES (?, ?, ?, 0)",
            [
                ("Review the active work queue", "General", "High"),
                ("Choose the next project milestone", "Project", "High"),
                ("Schedule a learning session", "Learning", "Medium"),
                ("Check the dashboard backup plan", "Homelab", "Low"),
            ],
        )


def seed_learning_data(conn: sqlite3.Connection) -> None:
    learning_count = conn.execute("SELECT COUNT(*) FROM learning_items").fetchone()[0]
    if learning_count != 0:
        return
    conn.executemany(
        """
        INSERT INTO learning_items
        (title, provider, url, status, progress, current_topic, next_action)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "Identity fundamentals study plan",
                "Learning resource",
                "",
                "Active",
                25,
                "Choose your current module",
                "Add the course link and next study action",
            ),
            (
                "DevOps course",
                "Learning resource",
                "",
                "Active",
                None,
                "Course in progress",
                "Add the course link and current module",
            ),
            (
                "Cloud certification study plan",
                "Learning resource",
                "",
                "Planned",
                0,
                "Select a certification path",
                "Add the official learning resource",
            ),
        ],
    )


def fetch_all(query: str, params: tuple = ()) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def fetch_one(query: str, params: tuple = ()) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


def execute(query: str, params: tuple = ()) -> None:
    with get_connection() as conn:
        conn.execute(query, params)
