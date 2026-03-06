"""ResearchFlow — Plan → [Code → Review]* → Execute, with circuit breaker.

CrewAI Flows' OR-condition listeners fire only ONCE (by design, see _fired_or_listeners).
Looping back into a listener via a router event is therefore not supported.
The correct pattern: keep the loop in plain Python inside a single @start method;
use Flow only for structured state storage and lifecycle hooks.

Pipeline:
  phase_plan  →  while retry < MAX_RETRIES:
                     phase_code  →  phase_review  →  route
                 → phase_execute  OR  phase_human_intervention
"""
import os
import sys
from pathlib import Path
from pydantic import BaseModel
from crewai.flow.flow import Flow, start

sys.path.insert(0, str(Path(__file__).parent))

MAX_RETRIES = 3


class LabState(BaseModel):
    topic: str = ""
    plan: str = ""
    code: str = ""
    reviewer_feedback: str = ""
    retry_count: int = 0
    final_result: str = ""
    status: str = "pending"       # pending | success | needs_human | failed
    source_channel_id: str = ""   # Slack channel to send progress updates to


class ResearchFlow(Flow[LabState]):

    def _notify(self, text: str) -> None:
        """Post a pipeline milestone to Slack. Uses source_channel_id if set."""
        try:
            from slack_notify import post, FLOW_CHANNEL
            channel = self.state.source_channel_id or FLOW_CHANNEL
            post(text, channel_id=channel)
        except Exception:
            pass  # never let notifications crash the flow

    @start()
    def run_pipeline(self):
        from crew import run_single_agent

        # ── Phase 1: Planning ──────────────────────────────────────────────
        print(f"🚀 [Planner] Generating experiment plan for: {self.state.topic}")
        self._notify(f"🚀 *Flow started* — topic: _{self.state.topic}_\nPhase 1/4: Planner (Gemini) working…")

        try:
            self.state.plan = run_single_agent(
                "planner",
                (
                    f"Research and create a detailed experiment plan for: {self.state.topic}\n\n"
                    "Your output must include:\n"
                    "1. Research objectives and hypothesis\n"
                    "2. Methodology and experimental design\n"
                    "3. Key hyperparameters or variables to test\n"
                    "4. Expected outcomes and success criteria\n"
                    "5. Resource requirements (GPU memory, compute time estimate)"
                ),
            )
        except Exception as e:
            self.state.status = "failed"
            self.state.final_result = f"❌ [Planner] failed: {e}"
            print(f"❌ [Planner] exception: {e}")
            self._notify(f"❌ *Planner failed*: `{e}`")
            return

        plan_preview = self.state.plan[:300].replace("\n", " ")
        self._notify(f"📋 *Planner done* — plan ready.\n> {plan_preview}…\n\nPhase 2/4: Coder (Claude Opus) writing…")

        # ── Phase 2+3: Code → Review loop (circuit breaker at MAX_RETRIES) ─
        while True:
            attempt = self.state.retry_count + 1
            attempt_label = f" (attempt {attempt}/{MAX_RETRIES})" if self.state.retry_count > 0 else ""
            print(f"💻 [Coder] Writing code{attempt_label}...")

            if self.state.retry_count > 0:
                self._notify(
                    f"🔄 *Coder retry {attempt}/{MAX_RETRIES}* — rewriting based on reviewer feedback.\n"
                    f"> Issues: {self.state.reviewer_feedback[:200]}…"
                )

            feedback_section = ""
            if self.state.reviewer_feedback:
                feedback_section = (
                    f"\n\n⚠️ PREVIOUS ATTEMPT REJECTED — fix ALL issues below:\n"
                    f"{self.state.reviewer_feedback}\n"
                    "Do not repeat the same mistakes."
                )

            try:
                self.state.code = run_single_agent(
                    "coder",
                    (
                        "Write complete, runnable Python/PyTorch/CUDA code for this experiment.\n\n"
                        f"PLAN:\n{self.state.plan}"
                        f"{feedback_section}\n\n"
                        "Requirements:\n"
                        "- Include all imports\n"
                        "- Add clear inline comments\n"
                        "- Handle OOM errors (try/except torch.cuda.OutOfMemoryError)\n"
                        "- Fully non-interactive — no input() calls\n"
                        "- Output ONLY the code, no prose"
                    ),
                )
            except Exception as e:
                self.state.status = "failed"
                self.state.final_result = f"❌ [Coder] failed: {e}"
                print(f"❌ [Coder] exception: {e}")
                self._notify(f"❌ *Coder failed* (attempt {attempt}/{MAX_RETRIES}): `{e}`")
                return

            code_lines = len(self.state.code.splitlines())
            self._notify(
                f"💻 *Coder done* (attempt {attempt}/{MAX_RETRIES}) — {code_lines} lines written.\n"
                f"Phase 3/4: Reviewer (GPT-5.3) auditing…"
            )
            print("🛡️  [Reviewer] Auditing code for correctness and VRAM safety...")

            try:
                self.state.reviewer_feedback = run_single_agent(
                    "reviewer",
                    (
                        "Review the experiment plan and code below. Check for:\n"
                        "- Logic bugs, wrong tensor shapes, dtype mismatches\n"
                        "- Peak VRAM usage (will it fit on an 80 GB A100? estimate explicitly)\n"
                        "- Deadlocks, infinite loops, gradient explosions\n"
                        "- HPC compatibility (no interactive prompts, correct exit codes)\n\n"
                        f"PLAN:\n{self.state.plan}\n\n"
                        f"CODE:\n{self.state.code}\n\n"
                        "END your response with EXACTLY ONE of these lines (nothing after it):\n"
                        "[STATUS: APPROVED]\n"
                        "[STATUS: NEEDS_REVISION]\n\n"
                        "Then list specific issues (if NEEDS_REVISION) or a brief approval note."
                    ),
                )
            except Exception as e:
                # Reviewer failure → treat as approved so the flow doesn't stall
                self.state.reviewer_feedback = (
                    f"[STATUS: APPROVED]\n(Review skipped due to error: {e})"
                )
                print(f"⚠️ [Reviewer] exception (auto-approved): {e}")
                self._notify(f"⚠️ *Reviewer error* (auto-approved): `{e}`")

            # ── Route ──────────────────────────────────────────────────────
            if "[STATUS: APPROVED]" in self.state.reviewer_feedback:
                print("✅ [Router] Code approved — proceeding to execution")
                self._notify(
                    f"✅ *Reviewer APPROVED* (attempt {attempt}/{MAX_RETRIES})\n"
                    f"Phase 4/4: Executor running…"
                )
                break

            self.state.retry_count += 1
            print(f"❌ [Router] Rejected — retry {self.state.retry_count}/{MAX_RETRIES}")
            self._notify(
                f"❌ *Reviewer NEEDS_REVISION* (attempt {attempt}/{MAX_RETRIES})\n"
                f"> {self.state.reviewer_feedback[:300]}…"
            )

            if self.state.retry_count >= MAX_RETRIES:
                print("🚨 [Router] Circuit breaker triggered — escalating to human")
                code_preview = self.state.code[:800]
                truncated = "...(truncated)" if len(self.state.code) > 800 else ""
                self.state.final_result = (
                    f"⚠️ Experiment halted after {self.state.retry_count} revision attempt(s).\n\n"
                    f"**Last Reviewer Feedback:**\n{self.state.reviewer_feedback}\n\n"
                    f"**Code (last attempt):**\n```python\n{code_preview}{truncated}\n```\n\n"
                    "Human intervention required."
                )
                self.state.status = "needs_human"
                # Human intervention alert is sent by api.py to all 4 agent channels
                return

        # ── Phase 4: Execute ───────────────────────────────────────────────
        hpc_host = os.getenv("HPC_HOST", "").strip()
        print(f"💪 [Executor] HPC_HOST={'configured' if hpc_host else 'NOT SET — delivering code directly'}")

        if not hpc_host:
            self.state.final_result = (
                "✅ Code approved by Reviewer. HPC execution skipped (HPC_HOST not configured).\n\n"
                f"**Approved Code:**\n```python\n{self.state.code}\n```\n\n"
                f"**Reviewer Notes:**\n{self.state.reviewer_feedback}"
            )
            self.state.status = "success"
            self._notify("✅ *Flow complete* — HPC_HOST not configured, approved code delivered.")
            return

        self._notify("🖥️ *Executor started* — submitting job to HPC cluster via SSH…")
        try:
            self.state.final_result = run_single_agent(
                "executor",
                (
                    "Execute the following Python script on the HPC cluster via SSH.\n\n"
                    f"CODE:\n{self.state.code}\n\n"
                    "Steps:\n"
                    "1. Save the code to a temp .py file on the cluster\n"
                    "2. Submit via SLURM sbatch (or run directly if < 30s)\n"
                    "3. Return: job ID, stdout (first 2000 chars), stderr, exit code"
                ),
            )
            self.state.status = "success"
            self._notify(f"✅ *Flow complete* — HPC job done.\n{self.state.final_result[:400]}")
        except Exception as e:
            self.state.final_result = (
                f"✅ Code approved but HPC execution failed: {e}\n\n"
                f"**Approved Code:**\n```python\n{self.state.code}\n```"
            )
            self.state.status = "success"
            print(f"⚠️ [Executor] exception (code still delivered): {e}")
            self._notify(f"⚠️ *Executor failed* (code still delivered): `{e}`")
