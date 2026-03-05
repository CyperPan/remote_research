"""ResearchCrew — Planner(Gemini) → Reviewer(GPT) → Coder(Claude) → Executor(Claude Haiku)

4-dimension optimisation applied:
  1. Temperature: Planner=0.8 (creative), Coder=0.15 (precise), Reviewer=0.0, Executor=0.0
  2. Tools: Planner gets ArxivPaperTool+BraveSearchTool; Coder gets PyLintTool;
            Reviewer gets CalculatorTool; Executor keeps HPCSSHTool
  3. Few-shot prompts: in config/agents.yaml
  4. Memory: memory=True with OpenAI text-embedding-3-small embedder
"""
import os, sys
from pathlib import Path
from crewai import Agent, Task, Crew, Process, LLM
from crewai.project import CrewBase, agent, task, crew

sys.path.insert(0, str(Path(__file__).parent))
from tools.hpc_ssh_tool import HPCSSHTool
from tools.pylint_tool import PyLintTool
from tools.calculator_tool import CalculatorTool

# ── Optional research tools (may not be installed in all envs) ────────────
try:
    from crewai_tools import ArxivPaperTool
    _arxiv_tool = ArxivPaperTool()
except Exception:
    _arxiv_tool = None

try:
    from crewai_tools import BraveSearchTool
    _brave_tool = BraveSearchTool(api_key=os.getenv("BRAVE_API_KEY", ""))
except Exception:
    _brave_tool = None

_PLANNER_TOOLS = [t for t in [_arxiv_tool, _brave_tool] if t is not None]


# ── LLM factories ─────────────────────────────────────────────────────────

def _gemini(model: str = "gemini/gemini-3.1-pro-preview", temperature: float = 0.8) -> LLM:
    """Google Gemini via LiteLLM. Uses GOOGLE_API_KEY."""
    return LLM(model=model, api_key=os.getenv("GOOGLE_API_KEY"), temperature=temperature)


def _openai(model: str = "openai/gpt-5.3-chat-latest", temperature: float = 1.0) -> LLM:
    """OpenAI via LiteLLM. Uses OPENAI_API_KEY.
    Note: o-series reasoning models (o1/o3/gpt-5.x) only support temperature=1 (the default).
    """
    return LLM(model=model, api_key=os.getenv("OPENAI_API_KEY"), temperature=temperature)


def _anthropic(model: str = "anthropic/claude-opus-4-6", temperature: float = 0.15) -> LLM:
    """Anthropic via native provider. Uses ANTHROPIC_API_KEY."""
    return LLM(model=model, api_key=os.getenv("ANTHROPIC_API_KEY"), temperature=temperature)


@CrewBase
class ResearchCrew:
    agents_config = str(Path(__file__).parent / "config" / "agents.yaml")
    tasks_config  = str(Path(__file__).parent / "config" / "tasks.yaml")

    # ── Agents ────────────────────────────────────────────────────────────────

    @agent
    def planner(self) -> Agent:
        """Gemini — creative planning + literature search (temperature=0.8)."""
        return Agent(
            config=self.agents_config["planner"],
            llm=_gemini("gemini/gemini-3.1-pro-preview", temperature=0.8),
            tools=_PLANNER_TOOLS,
            verbose=True,
        )

    @agent
    def reviewer(self) -> Agent:
        """OpenAI GPT — code review + math verification (temperature=1.0, o-series default)."""
        return Agent(
            config=self.agents_config["reviewer"],
            llm=_openai("openai/gpt-5.3-chat-latest", temperature=1.0),
            tools=[CalculatorTool()],
            verbose=True,
        )

    @agent
    def coder(self) -> Agent:
        """Claude Opus — low-temperature code generation + pylint self-check (temperature=0.15)."""
        return Agent(
            config=self.agents_config["coder"],
            llm=_anthropic("anthropic/claude-opus-4-6", temperature=0.15),
            tools=[PyLintTool()],
            verbose=True,
        )

    @agent
    def executor(self) -> Agent:
        """Claude Haiku — deterministic HPC orchestration via SSH (temperature=0.0)."""
        return Agent(
            config=self.agents_config["executor"],
            llm=_anthropic("anthropic/claude-haiku-4-5-20251001", temperature=0.0),
            tools=[HPCSSHTool()],
            verbose=True,
        )

    # ── Tasks ─────────────────────────────────────────────────────────────────

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config["research_task"])

    @task
    def review_task(self) -> Task:
        return Task(config=self.tasks_config["review_task"])

    @task
    def code_task(self) -> Task:
        return Task(config=self.tasks_config["code_task"])

    @task
    def execute_task(self) -> Task:
        return Task(config=self.tasks_config["execute_task"])

    # ── Crew ──────────────────────────────────────────────────────────────────

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.planner(), self.reviewer(), self.coder(), self.executor()],
            tasks=[self.research_task(), self.review_task(), self.code_task(), self.execute_task()],
            process=Process.sequential,
            memory=True,
            embedder={
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small",
                    "api_key": os.getenv("OPENAI_API_KEY"),
                },
            },
            verbose=True,
        )


# ── Single-agent runner (used by /agent/kickoff and flow.py) ───────────────

def run_single_agent(agent_name: str, task_description: str, inputs: dict | None = None) -> str:
    """Spin up a mini-crew with exactly one named agent and run it.

    Args:
        agent_name: one of 'planner', 'reviewer', 'coder', 'executor'
        task_description: the user's raw task/question as a string
        inputs: optional extra variables passed to kickoff

    Returns:
        The agent's response as a plain string.
    """
    _AGENTS = {
        "planner": lambda: Agent(
            role="Senior AI Systems Research Planner",
            goal=(
                "Produce a structured experiment plan with clear objectives, methodology, "
                "hyperparameter search space, and explicit GPU/VRAM budgets. "
                "Match complexity to the task — a Hello World needs 1 line, not a pipeline."
            ),
            backstory=(
                "You are a senior researcher at a top ML lab with 10+ years designing "
                "distributed training experiments. You write minimal plans for simple tasks "
                "and detailed plans only for complex ones."
            ),
            llm=_gemini("gemini/gemini-3.1-pro-preview", temperature=0.8),
            tools=_PLANNER_TOOLS,
            verbose=True,
        ),
        "reviewer": lambda: Agent(
            role="Principal ML Code Reviewer & VRAM Safety Auditor",
            goal=(
                "Review Python/PyTorch/CUDA code for bugs, VRAM overflow, and HPC compatibility. "
                "Always compute VRAM explicitly using: params_gb = N × bytes / 1024³. "
                "End with exactly [STATUS: APPROVED] or [STATUS: NEEDS_REVISION]."
            ),
            backstory=(
                "You are a principal engineer who has reviewed 1000+ ML experiment scripts. "
                "You catch shape bugs, fp16 overflow, and HPC-incompatible code instantly. "
                "For trivial/correct code you approve immediately without over-engineering."
            ),
            llm=_openai("openai/gpt-5.3-chat-latest", temperature=1.0),
            tools=[CalculatorTool()],
            verbose=True,
        ),
        "coder": lambda: Agent(
            role="Expert HPC Python & CUDA Engineer",
            goal=(
                "Write complete, immediately-runnable Python code. "
                "Match length to complexity — simple tasks get simple code. "
                "Always handle torch.cuda.OutOfMemoryError. Never use input(). "
                "Output ONLY the code with no prose."
            ),
            backstory=(
                "You are a staff engineer who ships distributed training code on GPU clusters. "
                "You write exactly what the plan asks for — no more, no less."
            ),
            llm=_anthropic("anthropic/claude-opus-4-6", temperature=0.15),
            tools=[PyLintTool()],
            verbose=True,
        ),
        "executor": lambda: Agent(
            role="HPC Cluster Operator",
            goal=(
                "Execute scripts on the remote HPC cluster via SSH using HPCSSHTool. "
                "Return: job ID, stdout (first 2000 chars), stderr, exit code."
            ),
            backstory=(
                "You are a battle-hardened HPC sysadmin who runs SLURM jobs daily. "
                "You report results clearly and handle failures gracefully."
            ),
            llm=_anthropic("anthropic/claude-haiku-4-5-20251001", temperature=0.0),
            tools=[HPCSSHTool()],
            verbose=True,
        ),
    }

    if agent_name not in _AGENTS:
        raise ValueError(f"Unknown agent {agent_name!r}. Valid: {sorted(_AGENTS)}")

    agent_obj = _AGENTS[agent_name]()
    task_obj = Task(
        description=task_description,
        expected_output="A detailed, well-structured response to the task.",
        agent=agent_obj,
    )
    mini_crew = Crew(
        agents=[agent_obj],
        tasks=[task_obj],
        process=Process.sequential,
        verbose=True,
    )
    result = mini_crew.kickoff(inputs=inputs or {})
    return result.raw if hasattr(result, "raw") else str(result)
