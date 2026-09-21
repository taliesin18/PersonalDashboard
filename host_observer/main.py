"""Read-only API that translates host status into the dashboard's neutral schema."""

from fastapi import FastAPI

from app.services.host_probe import host_snapshot


app = FastAPI(
    title="Dashboard Host Observer",
    version="0.1.0",
    description="Private, read-only host metrics and listening-service observer.",
)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "dashboard-host-observer"}


@app.get("/api/v1/host")
def host() -> dict:
    return host_snapshot()
