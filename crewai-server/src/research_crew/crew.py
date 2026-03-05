"""ResearchCrew — Planner(Gemini) → Reviewer(GPT) → Coder(Claude) → Executor(Claude Haiku)"""
import os, sys
from pathlib import Path
from crewai import Agent, Task, Crew, Process, LLM
from crewai.project import CrewBase, agent, task, crew

sys.path.insert(0, str(Path(__file__).parent))
from tools.hpc_ssh_tool import HPCSSHTool


def _gemini(model: str = "gemini/gemini-3.1-pro-preview") -> LLM:
    """Google Gemini via LiteLLM. Uses GOOGLE_API_KEY."""
    return LLM(model=model, api_key=os.getenv("GOOGLE_API_KEY"))


def _openai(model: str = "openai/gpt-5.3-chat-latest") -> LLM:
    """OpenAI via LiteLLM. Uses OPENAI_API_KEY.
    Note: update model string here when OpenAI releases newer SOTA models.
    """
    return LLM(model=model, api_key=os.getenv("OPENAI_API_KEY"))


def _anthropic(model: str = "anthropic/claude-opus-4-6") -> LLM:
    """Anthropic via native provider. Uses ANTHROPIC_API_KEY."""
    return LLM(model=model, api_key=os.getenv("ANTHROPIC_API_KEY"))


@CrewBase
class ResearchCrew:
    agents_config = str(Path(__file__).parent / "config" / "agents.yaml")
    tasks_config  = str(Path(__file__).parent / "config" / "tasks.yaml")

    # ── Agents ────────────────────────────────────────────────────────────────

    @agent
    def planner(self) -> Agent:
        """Gemini 2.5 Pro — deep research and planning."""
        return Agent(
            config=self.agents_config["planner"],
            llm=_gemini("gemini/gemini-3.1-pro-preview"),
            verbose=True,
        )

    @agent
    def reviewer(self) -> Agent:
        """OpenAI GPT-4.5 — task review and quality assurance."""
        return Agent(
            config=self.agents_config["reviewer"],
            llm=_openai("openai/gpt-5.3-chat-latest"),
            verbose=True,
        )

    @agent
    def coder(self) -> Agent:
        """Claude Opus 4.6 — code generation."""
        return Agent(
            config=self.agents_config["coder"],
            llm=_anthropic("anthropic/claude-opus-4-6"),
            verbose=True,
        )

    @agent
    def executor(self) -> Agent:
        """Claude Haiku 4.5 — lightweight HPC orchestration via SSH."""
        return Agent(
            config=self.agents_config["executor"],
            llm=_anthropic("anthropic/claude-haiku-4-5"),
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
            verbose=True,
        )


# ── Single-agent runner (used by /agent/kickoff) ───────────────────────────

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
            role="Research Planner",
            goal="Produce a thorough, well-structured research plan or analysis for the given task.",
            backstory=(
                "You are a senior HPC and deep-learning researcher. "
                "You excel at breaking complex problems into clear steps and surfacing relevant literature."
            ),
            llm=_gemini("gemini/gemini-3.1-pro-preview"),
            verbose=True,
        ),
        "reviewer": lambda: Agent(
            role="Quality Reviewer",
            goal="Review, critique, and improve the given content, code, or proposal. Flag issues clearly.",
            backstory=(
                "You are a meticulous technical reviewer with expertise in ML systems and HPC. "
                "You provide concise, actionable feedback."
            ),
            llm=_openai("openai/gpt-5.3-chat-latest"),
            verbose=True,
        ),
        "coder": lambda: Agent(
            role="Python Engineer",
            goal="Write clean, correct, production-ready Python (or CUDA/C++) code for the given task.",
            backstory=(
                "You are an expert Python/CUDA engineer specialising in HPC, LLM inference, and distributed systems. "
                "You write code that is readable and immediately runnable."
            ),
            llm=_anthropic("anthropic/claude-opus-4-6"),
            verbose=True,
        ),
        "executor": lambda: Agent(
            role="HPC Executor",
            goal="Execute commands or scripts on the HPC cluster via SSH and report results.",
            backstory=(
                "You are a systems engineer who runs jobs on HPC infrastructure. "
                "You use the HPCSSHTool to connect, submit, and monitor work."
            ),
            llm=_anthropic("anthropic/claude-haiku-4-5"),
            tools=[HPCSSHTool()],
            verbose=True,
        ),
    }

    if agent_name not in _AGENTS:
        raise ValueError(f"Unknown agent {agent_name!r}. Valid: {sorted(_AGENTS)}")

    agent = _AGENTS[agent_name]()
    task = Task(
        description=task_description,
        expected_output="A detailed, well-structured response to the task.",
        agent=agent,
    )
    mini_crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )
    result = mini_crew.kickoff(inputs=inputs or {})
    return result.raw if hasattr(result, "raw") else str(result)
