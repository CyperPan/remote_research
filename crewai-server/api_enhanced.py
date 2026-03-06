"""Enhanced CrewAI API Server with Agent Skills Integration"""
import os
import sys
import subprocess
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Add crew source to path
sys.path.insert(0, str(Path(__file__).parent / "src" / "research_crew"))

import jobs as job_store
from skills import validate_skills, get_skill_context

# Enhanced imports
try:
    from crew_enhanced import EnhancedResearchCrew, run_single_agent
    ENHANCED_MODE = True
except ImportError:
    from crew import ResearchCrew, run_single_agent
    ENHANCED_MODE = False

# ── Available crews registry ────────────────────────────────────────────────
CREWS = {
    "research": {
        "description": "Planner → Reviewer → Coder → Executor pipeline with skill integration. "
                      "Researches a topic, reviews findings, writes and runs code on HPC.",
        "inputs": ["topic", "code_required", "execute_on_hpc", "job_id"],
        "required": ["topic"],
        "skills": ["planner", "reviewer", "coder", "executor"]
    },
}

# ── API Lifespan & Health ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with skill validation."""
    print("🔍 Validating agent skills...")
    skill_validation = validate_skills()
    
    if all(skill_validation.values()):
        print("✅ All agent skills validated successfully")
        if ENHANCED_MODE:
            print("🚀 Running in ENHANCED mode with skill integration")
        else:
            print("⚙️  Running in STANDARD mode")
    else:
        print("⚠️  Some skills missing:", [k for k,v in skill_validation.items() if not v])
    
    print("CrewAI API Server ready on :8000")
    yield
    print("Shutting down CrewAI API Server...")

app = FastAPI(title="Enhanced CrewAI API Server", lifespan=lifespan)

# ── Enhanced Request Models ────────────────────────────────────────────────

class KickoffRequest(BaseModel):
    crew: str
    inputs: dict = {}
    use_skills: bool = True  # Enable skill-enhanced mode

class AgentKickoffRequest(BaseModel):
    agent: str   # planner | reviewer | coder | executor
    task: str    # the user's raw task/question
    inputs: dict = {}
    use_skills: bool = True  # Enable skill-enhanced mode

class FlowKickoffRequest(BaseModel):
    topic: str
    use_skills: bool = True  # Enable skill-enhanced mode

# ── Skill Information Endpoints ────────────────────────────────────────────

@app.get("/skills/available")
def list_available_skills():
    """List all available agent skills and their status."""
    validation = validate_skills()
    
    return {
        "skills": {
            "planner": {
                "name": "Research & Planning Specialist",
                "available": validation["planner"],
                "tools": ["ArxivPaperTool", "BraveSearchTool"],
                "description": "Literature research, trend analysis, experimental design"
            },
            "reviewer": {
                "name": "Code Quality & Safety Auditor", 
                "available": validation["reviewer"],
                "tools": ["CalculatorTool", "PyLintTool"],
                "description": "Code review, math verification, safety audit"
            },
            "coder": {
                "name": "HPC Python & CUDA Engineer",
                "available": validation["coder"],
                "tools": ["PyLintTool"],
                "description": "Code generation, HPC optimization, self-validation"
            },
            "executor": {
                "name": "HPC Cluster Operations Specialist",
                "available": validation["executor"],
                "tools": ["HPCSSHTool"],
                "description": "Cluster access, job management, execution monitoring"
            }
        },
        "enhanced_mode": ENHANCED_MODE,
        "all_skills_available": all(validation.values())
    }

@app.get("/skills/{agent_name}")
def get_agent_skill(agent_name: str):
    """Get detailed skill information for specific agent."""
    if agent_name not in ["planner", "reviewer", "coder", "executor"]:
        raise HTTPException(400, f"Unknown agent: {agent_name}")
    
    skill_context = get_skill_context(agent_name)
    validation = validate_skills()
    
    return {
        "agent": agent_name,
        "available": validation[agent_name],
        "skill_context": skill_context,
        "enhanced_features": ENHANCED_MODE
    }

# ── Enhanced Crew Management ───────────────────────────────────────────────

@app.get("/crew/list")
def list_crews():
    """List available crews with skill information."""
    return {
        "crews": CREWS,
        "enhanced_mode": ENHANCED_MODE,
        "skill_integration": True
    }

@app.post("/crew/kickoff")
def kickoff(req: KickoffRequest):
    """Enhanced crew kickoff with skill integration."""
    if req.crew not in CREWS:
        raise HTTPException(404, f"Crew '{req.crew}' not found. Available: {list(CREWS)}")
    
    required = CREWS[req.crew]["required"]
    missing = [k for k in required if k not in req.inputs]
    if missing:
        raise HTTPException(422, f"Missing required inputs: {missing}")

    job_id = job_store.create_job(req.crew, req.inputs)
    
    # Add skill context to inputs if enabled
    if req.use_skills and ENHANCED_MODE:
        req.inputs["skill_mode"] = "enhanced"
        req.inputs["agent_skills"] = CREWS[req.crew]["skills"]
    
    thread = threading.Thread(
        target=_run_crew_thread,
        args=(job_id, req.crew, req.inputs, req.use_skills),
        daemon=True,
    )
    thread.start()
    return {"job_id": job_id, "status": "queued", "crew": req.crew, "enhanced": req.use_skills}

def _run_crew_thread(job_id: str, crew_name: str, inputs: dict, use_skills: bool):
    """Enhanced crew execution thread with skill integration."""
    job_store.update_job(job_id, status="running")
    try:
        if ENHANCED_MODE and use_skills:
            # Use enhanced crew with skills
            crew_instance = EnhancedResearchCrew()
            result = crew_instance.crew().kickoff(inputs=inputs)
        else:
            # Use standard crew
            from crew import ResearchCrew
            crew_instance = ResearchCrew()
            result = crew_instance.crew().kickoff(inputs=inputs)
        
        raw = result.raw if hasattr(result, "raw") else str(result)
        job_store.update_job(job_id, status="done", result=raw)
        _notify_openclaw(job_id, crew_name, raw)
    except Exception as exc:
        job_store.update_job(job_id, status="failed", error=str(exc))
        _notify_openclaw(job_id, crew_name, f"FAILED: {exc}")

# ── Enhanced Single-Agent Endpoints ────────────────────────────────────────

@app.post("/agent/kickoff")
def agent_kickoff(req: AgentKickoffRequest):
    """Enhanced single-agent kickoff with skill integration."""
    if req.agent not in ["planner", "reviewer", "coder", "executor"]:
        raise HTTPException(400, f"Unknown agent '{req.agent}'. Valid: {['planner', 'reviewer', 'coder', 'executor']}")
    if not req.task.strip():
        raise HTTPException(422, "Field 'task' must not be empty")

    job_id = job_store.create_job(f"agent:{req.agent}", {"task": req.task, **req.inputs})
    
    # Add skill context if enabled
    if req.use_skills:
        req.inputs["skill_mode"] = "enhanced"
        req.inputs["agent_name"] = req.agent
    
    threading.Thread(
        target=_run_agent_thread,
        args=(job_id, req.agent, req.task, req.inputs, req.use_skills),
        daemon=True,
    ).start()
    return {"job_id": job_id, "status": "queued", "agent": req.agent, "enhanced": req.use_skills}

def _run_agent_thread(job_id: str, agent_name: str, task: str, inputs: dict, use_skills: bool):
    """Enhanced agent execution with skill integration."""
    job_store.update_job(job_id, status="running")
    try:
        result = run_single_agent(agent_name, task, inputs)
        job_store.update_job(job_id, status="done", result=result)
        _notify_openclaw(job_id, f"agent:{agent_name}", result)
    except Exception as exc:
        job_store.update_job(job_id, status="failed", error=str(exc))
        _notify_openclaw(job_id, f"agent:{agent_name}", f"FAILED: {exc}")

# ── Enhanced Flow Endpoints ────────────────────────────────────────────────

@app.post("/flow/kickoff")
def flow_kickoff(req: FlowKickoffRequest):
    """Enhanced flow kickoff with skill integration."""
    if not req.topic.strip():
        raise HTTPException(422, "Field 'topic' must not be empty")
    
    job_id = job_store.create_job("flow:research", {"topic": req.topic, "skill_mode": req.use_skills})
    threading.Thread(target=_run_flow_thread, args=(job_id, req.topic, req.use_skills), daemon=True).start()
    return {"job_id": job_id, "status": "queued", "flow": "research", "enhanced": req.use_skills}

def _run_flow_thread(job_id: str, topic: str, use_skills: bool):
    """Enhanced flow execution with skill integration."""
    from research_crew.flow import ResearchFlow
    
    flow = ResearchFlow()
    flow.state.topic = topic
    flow.state.skill_mode = use_skills
    
    try:
        flow.kickoff(inputs={"topic": topic, "skill_mode": use_skills})
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

# ── Standard Endpoints (unchanged) ─────────────────────────────────────────

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

@app.get("/health")
def health():
    validation = validate_skills()
    return {
        "status": "ok",
        "enhanced_mode": ENHANCED_MODE,
        "skills_available": validation,
        "all_skills_ready": all(validation.values())
    }

# ── Utility Functions ───────────────────────────────────────────────────────

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


# Enhanced startup
if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Enhanced CrewAI API Server...")
    print(f"Enhanced Mode: {ENHANCED_MODE}")
    print(f"Skill System: {'Available' if ENHANCED_MODE else 'Standard'}")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")