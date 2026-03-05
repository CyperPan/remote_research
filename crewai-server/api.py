"""CrewAI API Server — FastAPI wrapper for triggering crews from OpenClaw."""
import os, sys, subprocess, threading
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Add crew source to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import jobs as job_store

# ── Available crews registry ───────────────────────────────────────────────
CREWS = {
    "research": {
        "description": "Planner → Reviewer → Coder → Executor pipeline. Researches a topic, reviews findings, optionally writes and runs code on HPC.",
        "inputs": ["topic", "code_required", "execute_on_hpc", "job_id"],
        "required": ["topic"],
    },
}


def _load_crew(crew_name: str):
    if crew_name == "research":
        from research_crew.crew import ResearchCrew
        return ResearchCrew()
    raise ValueError(f"Unknown crew: {crew_name}")


def _notify_openclaw(job_id: str, crew_name: str, summary: str):
    """Send a system event to the running OpenClaw gateway."""
    short = summary[:300].replace("'", "\\'")
    token = os.getenv("OPENCLAW_GATEWAY_TOKEN", "")
    nvm = "source ~/.nvm/nvm.sh 2>/dev/null"
    cmd = f'{nvm} && openclaw system event --text "Crew {crew_name} done (job {job_id[:8]}): {short}" --mode now'
    try:
        subprocess.run(["bash", "-c", cmd], timeout=10, capture_output=True)
    except Exception:
        pass  # notification is best-effort


def _run_crew_thread(job_id: str, crew_name: str, inputs: dict):
    job_store.update_job(job_id, status="running")
    try:
        crew_instance = _load_crew(crew_name)
        result = crew_instance.crew().kickoff(inputs={**inputs, "job_id": job_id})
        raw = result.raw if hasattr(result, "raw") else str(result)
        job_store.update_job(job_id, status="done", result=raw)
        _notify_openclaw(job_id, crew_name, raw)
    except Exception as exc:
        job_store.update_job(job_id, status="failed", error=str(exc))
        _notify_openclaw(job_id, crew_name, f"FAILED: {exc}")


# ── API ────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("CrewAI API Server ready on :8000")
    yield

app = FastAPI(title="CrewAI API Server", lifespan=lifespan)


class KickoffRequest(BaseModel):
    crew: str
    inputs: dict = {}


@app.get("/crew/list")
def list_crews():
    return {"crews": CREWS}


@app.post("/crew/kickoff")
def kickoff(req: KickoffRequest):
    if req.crew not in CREWS:
        raise HTTPException(404, f"Crew '{req.crew}' not found. Available: {list(CREWS)}")
    required = CREWS[req.crew]["required"]
    missing = [k for k in required if k not in req.inputs]
    if missing:
        raise HTTPException(422, f"Missing required inputs: {missing}")

    job_id = job_store.create_job(req.crew, req.inputs)
    thread = threading.Thread(
        target=_run_crew_thread,
        args=(job_id, req.crew, req.inputs),
        daemon=True,
    )
    thread.start()
    return {"job_id": job_id, "status": "queued", "crew": req.crew}


@app.get("/crew/status/{job_id}")
def status(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    return job


@app.post("/crew/cancel/{job_id}")
def cancel(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    if job["status"] not in ("queued", "running"):
        return {"message": f"Job already {job['status']}, cannot cancel"}
    job_store.update_job(job_id, status="cancelled")
    return {"message": "Cancel requested (in-flight tasks may still complete)"}


@app.get("/crew/jobs")
def list_jobs(limit: int = 20):
    return {"jobs": job_store.list_jobs(limit)}


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Single-agent endpoint ──────────────────────────────────────────────────

VALID_AGENTS = ["planner", "reviewer", "coder", "executor"]


class AgentKickoffRequest(BaseModel):
    agent: str   # planner | reviewer | coder | executor
    task: str    # the user's raw task/question
    inputs: dict = {}


def _run_agent_thread(job_id: str, agent_name: str, task: str, inputs: dict):
    job_store.update_job(job_id, status="running")
    try:
        from research_crew.crew import run_single_agent
        result = run_single_agent(agent_name, task, inputs)
        job_store.update_job(job_id, status="done", result=result)
        _notify_openclaw(job_id, f"agent:{agent_name}", result)
    except Exception as exc:
        job_store.update_job(job_id, status="failed", error=str(exc))
        _notify_openclaw(job_id, f"agent:{agent_name}", f"FAILED: {exc}")


@app.post("/agent/kickoff")
def agent_kickoff(req: AgentKickoffRequest):
    if req.agent not in VALID_AGENTS:
        raise HTTPException(400, f"Unknown agent '{req.agent}'. Valid: {VALID_AGENTS}")
    if not req.task.strip():
        raise HTTPException(422, "Field 'task' must not be empty")

    job_id = job_store.create_job(f"agent:{req.agent}", {"task": req.task, **req.inputs})
    threading.Thread(
        target=_run_agent_thread,
        args=(job_id, req.agent, req.task, req.inputs),
        daemon=True,
    ).start()
    return {"job_id": job_id, "status": "queued", "agent": req.agent}


# ── Flow endpoint ──────────────────────────────────────────────────────────

class FlowKickoffRequest(BaseModel):
    topic: str


def _run_flow_thread(job_id: str, topic: str):
    job_store.update_job(job_id, status="running")
    try:
        from research_crew.flow import ResearchFlow
        flow = ResearchFlow()
        flow.kickoff(inputs={"topic": topic})
        state = flow.state
        summary = (
            f"**Status:** {state.status}\n\n"
            f"**Retries:** {state.retry_count}/{3}\n\n"
            f"**Result:**\n{state.final_result}"
        )
        job_store.update_job(job_id, status="done", result=summary, state=state.model_dump())
        _notify_openclaw(job_id, "flow:research", summary)
    except Exception as exc:
        job_store.update_job(job_id, status="failed", error=str(exc))
        _notify_openclaw(job_id, "flow:research", f"FAILED: {exc}")


@app.post("/flow/kickoff")
def flow_kickoff(req: FlowKickoffRequest):
    if not req.topic.strip():
        raise HTTPException(422, "Field 'topic' must not be empty")
    job_id = job_store.create_job("flow:research", {"topic": req.topic})
    threading.Thread(target=_run_flow_thread, args=(job_id, req.topic), daemon=True).start()
    return {"job_id": job_id, "status": "queued", "flow": "research"}


# ── Flow state endpoint ────────────────────────────────────────────────────
# Stores full LabState JSON in job["state"], queryable after job completes.

@app.get("/flow/state/{job_id}")
def flow_state(job_id: str):
    """Return the full LabState for a flow job (plan, code, reviewer_feedback, etc.)"""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    if job.get("crew", "").startswith("flow:") is False:
        raise HTTPException(400, f"Job {job_id} is not a flow job")
    state = job.get("state")
    if not state:
        return {"job_id": job_id, "status": job["status"], "state": None,
                "note": "State not available yet (job still running or was created before this feature)"}
    return {"job_id": job_id, "status": job["status"], "state": state}
