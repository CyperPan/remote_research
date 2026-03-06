"""CrewAI API Server — FastAPI wrapper for triggering crews from OpenClaw."""
import os, sys, subprocess, threading
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import requests as _requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Add crew source to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import jobs as job_store

# ── Slack channel map ──────────────────────────────────────────────────────
# Channel IDs for the four agent-dedicated Slack channels.
SLACK_CHANNELS = {
    "planner":  "C0AJSUZ7MC5",
    "reviewer": "C0AJQ0WC3KM",
    "coder":    "C0AK00JUFEG",
    "executor": "C0AJWCSDQ10",   # channel named "excutor"
}
# General research channel — used for full-flow results
SLACK_GENERAL_CHANNEL = "C0AJW7E2GBU"   # #all-researchlab


def _post_to_slack(channel_id: str, text: str, *, source_channel_id: str = "") -> None:
    """Post a message to a Slack channel via the bot token. Best-effort."""
    token = os.getenv("SLACK_BOT_TOKEN", "")
    if not token:
        return
    target = source_channel_id or channel_id
    try:
        _requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"channel": target, "text": text, "unfurl_links": False},
            timeout=8,
        )
    except Exception:
        pass  # notification is best-effort


def _mention_owner() -> str:
    """Return Slack @mention string for the human owner."""
    uid = os.getenv("SLACK_OWNER_ID", "")
    return f"<@{uid}>" if uid else "@owner"


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
    """Send a system event to the running OpenClaw gateway (WhatsApp/Slack via OpenClaw)."""
    short = summary[:300].replace("'", "\\'")
    nvm = "source ~/.nvm/nvm.sh 2>/dev/null"
    cmd = f'{nvm} && openclaw system event --text "Crew {crew_name} done (job {job_id[:8]}): {short}" --mode now'
    try:
        subprocess.run(["bash", "-c", cmd], timeout=10, capture_output=True)
    except Exception:
        pass


def _run_crew_thread(job_id: str, crew_name: str, inputs: dict):
    job_store.update_job(job_id, status="running")
    src = inputs.get("source_channel_id", "")
    try:
        crew_instance = _load_crew(crew_name)
        result = crew_instance.crew().kickoff(inputs={**inputs, "job_id": job_id})
        raw = result.raw if hasattr(result, "raw") else str(result)
        job_store.update_job(job_id, status="done", result=raw)
        _notify_openclaw(job_id, crew_name, raw)
        _post_to_slack(SLACK_GENERAL_CHANNEL, f"✅ *{crew_name}* done (job `{job_id[:8]}`):\n{raw[:1200]}", source_channel_id=src)
    except Exception as exc:
        job_store.update_job(job_id, status="failed", error=str(exc))
        _notify_openclaw(job_id, crew_name, f"FAILED: {exc}")
        _post_to_slack(SLACK_GENERAL_CHANNEL, f"❌ *{crew_name}* failed (job `{job_id[:8]}`): {exc}", source_channel_id=src)


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
    agent: str              # planner | reviewer | coder | executor
    task: str               # the user's raw task/question
    inputs: dict = {}
    source_channel_id: str = ""  # Slack channel to reply to (set by SKILL.md)


def _run_agent_thread(job_id: str, agent_name: str, task: str, inputs: dict, source_channel_id: str = ""):
    job_store.update_job(job_id, status="running")
    default_channel = SLACK_CHANNELS.get(agent_name, SLACK_GENERAL_CHANNEL)
    try:
        from research_crew.crew import run_single_agent
        result = run_single_agent(agent_name, task, inputs)
        job_store.update_job(job_id, status="done", result=result)
        _notify_openclaw(job_id, f"agent:{agent_name}", result)
        _post_to_slack(
            default_channel,
            f"✅ *{agent_name}* done (job `{job_id[:8]}`):\n{result[:1500]}",
            source_channel_id=source_channel_id,
        )
    except Exception as exc:
        job_store.update_job(job_id, status="failed", error=str(exc))
        _notify_openclaw(job_id, f"agent:{agent_name}", f"FAILED: {exc}")
        _post_to_slack(
            default_channel,
            f"❌ *{agent_name}* failed (job `{job_id[:8]}`): {exc}",
            source_channel_id=source_channel_id,
        )


@app.post("/agent/kickoff")
def agent_kickoff(req: AgentKickoffRequest):
    if req.agent not in VALID_AGENTS:
        raise HTTPException(400, f"Unknown agent '{req.agent}'. Valid: {VALID_AGENTS}")
    if not req.task.strip():
        raise HTTPException(422, "Field 'task' must not be empty")

    job_id = job_store.create_job(f"agent:{req.agent}", {"task": req.task, **req.inputs})
    threading.Thread(
        target=_run_agent_thread,
        args=(job_id, req.agent, req.task, req.inputs, req.source_channel_id),
        daemon=True,
    ).start()
    return {"job_id": job_id, "status": "queued", "agent": req.agent}


# ── Flow endpoint ──────────────────────────────────────────────────────────

class FlowKickoffRequest(BaseModel):
    topic: str
    source_channel_id: str = ""  # Slack channel to reply to (set by SKILL.md)


def _run_flow_thread(job_id: str, topic: str, source_channel_id: str = ""):
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

        if state.status == "needs_human":
            # Alert the human owner in ALL four agent channels
            alert = (
                f"🚨 {_mention_owner()} *Human intervention required* (job `{job_id[:8]}`)\n\n"
                f"The autonomous flow hit the circuit breaker after {state.retry_count} retries.\n\n"
                f"*Last Reviewer Feedback:*\n{state.reviewer_feedback[:800]}\n\n"
                f"*Code (last attempt):*\n```python\n{state.code[:600]}\n```\n\n"
                "Please review and provide guidance."
            )
            for ch_id in SLACK_CHANNELS.values():
                _post_to_slack(ch_id, alert)
        else:
            # Post success result to source channel or general channel
            _post_to_slack(
                SLACK_GENERAL_CHANNEL,
                f"✅ *Research flow* done (job `{job_id[:8]}`, {state.retry_count} retries):\n{state.final_result[:1200]}",
                source_channel_id=source_channel_id,
            )
    except Exception as exc:
        job_store.update_job(job_id, status="failed", error=str(exc))
        _notify_openclaw(job_id, "flow:research", f"FAILED: {exc}")
        _post_to_slack(
            SLACK_GENERAL_CHANNEL,
            f"❌ {_mention_owner()} *Research flow* failed (job `{job_id[:8]}`): {exc}",
            source_channel_id=source_channel_id,
        )


@app.post("/flow/kickoff")
def flow_kickoff(req: FlowKickoffRequest):
    if not req.topic.strip():
        raise HTTPException(422, "Field 'topic' must not be empty")
    job_id = job_store.create_job("flow:research", {"topic": req.topic})
    threading.Thread(
        target=_run_flow_thread,
        args=(job_id, req.topic, req.source_channel_id),
        daemon=True,
    ).start()
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
