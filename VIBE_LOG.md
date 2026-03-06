# VIBE LOG — remote_research

A running record of completed work. Ordered chronologically.

---

## Phase 1 — Infrastructure Scaffold

**Repo init & hardware decision**
- Created GitHub repo `CyperPan/remote_research`
- Chose Jetson Orin Nano as bastion host (replaces original RPi design)
- Chose Tailscale as zero-trust network layer (replaces Cloudflare tunnel)

**Scripts & deployment files created**
- `deployments/docker-compose.yml` — ttyd terminal container (ARM64, port 7681, dark theme)
- `scripts/install_gateway.sh` — idempotent Jetson setup: Docker, Tailscale, ttyd container
- `scripts/setup_ssh_trust.sh` — generate ed25519 key + ssh-copy-id to MacBook
- `scripts/setup_macbook.sh` — clone Ninglo/remotelab, npm install, .env template, pm2 start
- `tests/test_scripts.sh` — bash -n syntax validation for all shell scripts
- `tests/test_docker.sh` — docker compose config validation
- `docs/SECURITY_POLICY.md` — ZTNA rules, SSH key lifecycle, Tailscale ACL guide
- `README.md` — Mermaid architecture diagram, 3-step quickstart
- `docs/DEVELOPMENT_GUIDE.md` — full setup walkthrough including Ninglo remotelab step

**Verified on Jetson**
- Tailscale installed and authenticated
- Docker + Compose pre-installed
- Python 3.10, pip, crewai, fastapi, paramiko installed in `.venv`

---

## Phase 2 — CrewAI Multi-Agent System

**FastAPI server (`crewai-server/api.py`)**
- `/health` — liveness probe
- `/crew/list`, `/crew/kickoff`, `/crew/status/{job_id}`, `/crew/cancel/{job_id}`, `/crew/jobs`
- `/agent/kickoff` — single-agent dispatch (planner / reviewer / coder / executor)
- `/flow/kickoff` — full autonomous pipeline kickoff
- `/flow/state/{job_id}` — inspect full LabState after flow completes
- Background thread execution with in-memory job store
- `_notify_openclaw()` — sends system event to OpenClaw gateway on job completion

**Agent configuration (`crew.py`)**
- `ResearchCrew` class with 4 agents wired to different LLM providers:
  - Planner → Gemini 3.1 Pro (temperature 0.8)
  - Reviewer → GPT-5.3 (temperature 1.0, o-series default)
  - Coder → Claude Opus 4.6 (temperature 0.15)
  - Executor → Claude Haiku 4.5 (temperature 0.0)
- `run_single_agent()` — mini-crew function for single-agent dispatch

**Research flow (`flow.py`)**
- `ResearchFlow` class using CrewAI Flows with Python `while` loop (not event listeners)
- Resolved CrewAI `_fired_or_listeners` bug — OR-condition listeners only fire once by design; fixed by moving loop into a single `@start()` method
- `LabState` Pydantic model: topic / plan / code / reviewer_feedback / retry_count / final_result / status / source_channel_id
- Circuit breaker at `MAX_RETRIES = 3`: triggers `needs_human` state after 3 rejections
- Reviewer routing via `[STATUS: APPROVED]` / `[STATUS: NEEDS_REVISION]` tags
- HPC execution gated on `HPC_HOST` env var; delivers approved code directly if unset

**Tools**
- `HPCSSHTool` — paramiko SSH executor for HPC cluster commands
- `PyLintTool` — runs pylint subprocess on code snippets, returns full report
- `CalculatorTool` — safe `eval()` with math namespace for VRAM / FLOPs arithmetic

**pm2 daemon**
- `crewai-api` process running on Jetson, auto-restart on crash

---

## Phase 3 — 4-Dimension Agent Optimization

**Temperature tuning**
- Planner: 0.8 (creative, generative)
- Coder: 0.15 (precise, low variance)
- Reviewer: 1.0 (forced — GPT o-series only accepts default temperature)
- Executor: 0.0 (deterministic)

**Tool assignment**
- Planner: `ArxivPaperTool` + `BraveSearchTool` (literature + web search)
- Coder: `PyLintTool` (self-lint before submitting)
- Reviewer: `CalculatorTool` (precise VRAM math)
- Executor: `HPCSSHTool`

**Few-shot prompts (`config/agents.yaml` rewrite)**
- Planner: complexity-matching rule ("Hello World → 1 line, not a pipeline") + two calibration examples
- Reviewer: VRAM formula + 7 known bug patterns + approval decision examples
- Coder: MoE TopKRouter template + style contract (✓/✗ checklist)
- Executor: SLURM execution protocol + structured return format

**Memory**
- `ResearchCrew` crew: `memory=True` with `text-embedding-3-small` (OpenAI embedder)

**Verified result:** Hello World flow completes in 38s with 0 retries, APPROVED on first pass (previously hit circuit breaker every time due to Planner over-engineering).

---

## Phase 4 — OpenClaw @mention Routing

**WhatsApp integration**
- `~/.openclaw/workspace/skills/crewai-control/SKILL.md` — skill that routes `@planner`, `@reviewer`, `@coder`, `@executor`, `@flow` prefixes to the CrewAI API
- `@flow <topic>` → `/flow/kickoff`
- `@<agent> <task>` → `/agent/kickoff`
- `@openclaw` or no prefix → native Claude Haiku (no crew)

---

## Phase 5 — Slack Integration

**Bot setup**
- OpenClaw Slack bot (`claw_crew` / `slack_mode`) connected to workspace `researchlab`
- Socket mode enabled
- Bot invited to 5 channels: `#planner`, `#reviewer`, `#coder`, `#excutor`, `#all-researchlab`

**Channel-based auto-routing (SKILL.md)**
- Message in `#planner` → auto-routes to Planner (no @prefix needed)
- Message in `#coder` → auto-routes to Coder
- Message in `#reviewer` → auto-routes to Reviewer
- Message in `#excutor` → auto-routes to Executor
- `source_channel_id` passed in every API call so results post back to originating channel

**Agent-to-channel notifications (`api.py` + `slack_notify.py`)**
- `slack_notify.py` — shared `post()` / `mention_owner()` helper
- Single-agent job done → result posted to agent's dedicated channel
- Single-agent job failed → error posted to agent's dedicated channel
- Flow success → final result posted to `#all-researchlab`
- Flow `needs_human` (circuit breaker) → `@owner` alert posted to **all 4 agent channels simultaneously**

**Real-time flow milestone notifications (`flow.py`)**
- Every key pipeline event posts to Slack in real time:
  - 🚀 Flow started (topic)
  - 📋 Planner done (plan preview)
  - 💻 Coder done (attempt N/3, line count)
  - 🔄 Coder retry N/3 (reviewer issue summary)
  - ✅ Reviewer APPROVED
  - ❌ Reviewer NEEDS_REVISION (feedback preview)
  - 🖥️ Executor started
  - ✅ Flow complete / ⚠️ Executor failed

---

## Current Verified State

| Component | Status |
|-----------|--------|
| Jetson CrewAI API (:8000) | ✅ Running (pm2) |
| OpenClaw WhatsApp gateway | ✅ Running |
| OpenClaw Slack gateway | ✅ Running (socket mode) |
| @mention routing (WhatsApp + Slack) | ✅ Working |
| Channel auto-routing (Slack) | ✅ Working |
| Agent result → channel push | ✅ Working |
| Flow milestone notifications | ✅ Working |
| Circuit breaker → @owner alert | ✅ Working |
| HPC executor (SSH) | ⬜ Pending HPC_HOST config |

---

*Last updated: 2026-03-06*
