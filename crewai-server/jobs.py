"""Thread-safe async job store with file persistence."""
import json, os, threading, uuid
from datetime import datetime
from pathlib import Path

JOBS_FILE = Path.home() / ".crewai-server" / "jobs.json"
JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()
_jobs: dict = {}


def _load():
    global _jobs
    if JOBS_FILE.exists():
        try:
            _jobs = json.loads(JOBS_FILE.read_text())
        except Exception:
            _jobs = {}


def _save():
    JOBS_FILE.write_text(json.dumps(_jobs, indent=2, default=str))


_load()


def create_job(crew_name: str, inputs: dict) -> str:
    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "crew": crew_name,
            "inputs": inputs,
            "status": "queued",
            "result": None,
            "error": None,
            "created_at": datetime.utcnow().isoformat(),
            "finished_at": None,
        }
        _save()
    return job_id


def update_job(job_id: str, **kwargs):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)
            if kwargs.get("status") in ("done", "failed"):
                _jobs[job_id]["finished_at"] = datetime.utcnow().isoformat()
            _save()


def get_job(job_id: str) -> dict | None:
    with _lock:
        return dict(_jobs.get(job_id, {}))


def list_jobs(limit: int = 20) -> list:
    with _lock:
        return sorted(_jobs.values(), key=lambda j: j["created_at"], reverse=True)[:limit]
