"""Enhanced ResearchCrew with Agent Skills Integration"""
import os
import sys
from pathlib import Path
from crewai import Agent, Task, Crew, Process, LLM
from crewai.project import CrewBase, agent, task, crew

sys.path.insert(0, str(Path(__file__).parent))
from tools.hpc_ssh_tool import HPCSSHTool
from tools.pylint_tool import PyLintTool
from tools.calculator_tool import CalculatorTool
from skills import get_skill_context, SkillUtils

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

# ── LLM factories with skill-aware configuration ──────────────────────────

def _gemini(model: str = "gemini/gemini-3.1-pro-preview", temperature: float = 0.8) -> LLM:
    """Google Gemini via LiteLLM with Planner agent optimization."""
    return LLM(
        model=model, 
        api_key=os.getenv("GOOGLE_API_KEY"), 
        temperature=temperature,
        # Add skill-specific parameters
        max_tokens=4096,
        top_p=0.95,
    )

def _openai(model: str = "openai/gpt-5.3-chat-latest", temperature: float = 1.0) -> LLM:
    """OpenAI via LiteLLM with Reviewer agent optimization."""
    return LLM(
        model=model, 
        api_key=os.getenv("OPENAI_API_KEY"), 
        temperature=temperature,
        # Optimize for code review and analysis
        max_tokens=2048,
    )

def _anthropic(model: str = "anthropic/claude-opus-4-6", temperature: float = 0.15) -> LLM:
    """Anthropic via native provider with Coder/Executor agent optimization."""
    return LLM(
        model=model, 
        api_key=os.getenv("ANTHROPIC_API_KEY"), 
        temperature=temperature,
        # Optimize for precise code generation
        max_tokens=8192,
    )

@CrewBase
class EnhancedResearchCrew:
    agents_config = str(Path(__file__).parent / "config" / "agents.yaml")
    tasks_config  = str(Path(__file__).parent / "config" / "tasks.yaml")

    # ── Enhanced Agents with Skill Integration ────────────────────────────────

    @agent
    def planner(self) -> Agent:
        """Enhanced Planner with research skills and literature expertise."""
        skill_context = get_skill_context("planner")
        
        return Agent(
            config=self.agents_config["planner"],
            llm=_gemini("gemini/gemini-3.1-pro-preview", temperature=0.8),
            tools=_PLANNER_TOOLS,
            verbose=True,
            # Enhanced role with skill context
            role="AI Research Specialist with Literature Expertise",
            goal=(
                "Conduct comprehensive literature reviews, identify research gaps, "
                "and design evidence-based experimental plans. Leverage Arxiv and web "
                "search to provide current, relevant research foundation."
            ),
            backstory=(
                f"{skill_context} You are a senior researcher with deep expertise in "
                "machine learning literature, able to synthesize complex information "
                "from multiple sources and identify promising research directions."
            ),
        )

    @agent
    def reviewer(self) -> Agent:
        """Enhanced Reviewer with comprehensive code audit capabilities."""
        skill_context = get_skill_context("reviewer")
        
        return Agent(
            config=self.agents_config["reviewer"],
            llm=_openai("openai/gpt-5.3-chat-latest", temperature=1.0),
            tools=[CalculatorTool()],
            verbose=True,
            # Enhanced role with skill context
            role="Principal Engineer & Code Safety Auditor",
            goal=(
                "Perform comprehensive code reviews with mathematical verification, "
                "VRAM safety analysis, and HPC compatibility checks. Use CalculatorTool "
                "for precise resource estimation."
            ),
            backstory=(
                f"{skill_context} You are a principal engineer who has reviewed thousands "
                "of ML experiments, with expertise in catching subtle bugs, memory issues, "
                "and performance bottlenecks before they reach production."
            ),
        )

    @agent
    def coder(self) -> Agent:
        """Enhanced Coder with HPC optimization expertise."""
        skill_context = get_skill_context("coder")
        
        return Agent(
            config=self.agents_config["coder"],
            llm=_anthropic("anthropic/claude-opus-4-6", temperature=0.15),
            tools=[PyLintTool()],
            verbose=True,
            # Enhanced role with skill context
            role="Expert HPC Engineer & Code Generator",
            goal=(
                "Generate production-ready, optimized code for GPU clusters. "
                "Use PyLintTool for self-validation and ensure HPC compatibility "
                "with proper error handling and performance optimization."
            ),
            backstory=(
                f"{skill_context} You are a staff engineer specializing in distributed "
                "training systems, with deep knowledge of PyTorch, CUDA, and HPC "
                "optimization techniques for large-scale ML workloads."
            ),
        )

    @agent
    def executor(self) -> Agent:
        """Enhanced Executor with NU Explorer HPC expertise."""
        skill_context = get_skill_context("executor")
        explorer_context = self._get_explorer_hpc_context()
        
        return Agent(
            config=self.agents_config["executor"],
            llm=_anthropic("anthropic/claude-haiku-4-5-20251001", temperature=0.0),
            tools=[HPCSSHTool()],
            verbose=True,
            # Enhanced role with skill context
            role="NU Explorer HPC Cluster Operations Specialist",
            goal=(
                "Execute research code on Northeastern Explorer HPC cluster. "
                "Manage Slurm job allocation, GPU resources, and environment setup "
                "using HPCSSHTool for remote execution."
            ),
            backstory=(
                f"{skill_context} {explorer_context} You are a battle-hardened HPC "
                "sysadmin with specific expertise in NU Explorer operations, SLURM "
                "workload management, and GPU cluster administration."
            ),
        )

    def _get_explorer_hpc_context(self) -> str:
        """Get NU Explorer HPC specific context."""
        explorer_skill_path = Path(__file__).parent / "skills" / "explorer_hpc_skill.md"
        if explorer_skill_path.exists():
            content = explorer_skill_path.read_text()
            # Extract key information for context
            lines = content.split('\n')
            key_info = []
            
            for line in lines[:50]:  # First 50 lines contain key specs
                if any(keyword in line.lower() for keyword in 
                       ['v100-sxm2', 'explorer', 'slurm', 'gpu partition']):
                    key_info.append(line.strip())
            
            return "Specific NU Explorer expertise: " + " ".join(key_info[:5])
        
        return "NU Explorer HPC cluster operations specialist."

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

    # ── Enhanced Crew with Skill Integration ──────────────────────────────────

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
            # Add skill-aware configuration
            context={
                "skill_system": "enabled",
                "agent_specialization": True,
                "hpc_optimization": True,
            },
        )


# ── Enhanced Single-agent Runner ────────────────────────────────────────────

def run_single_agent(agent_name: str, task_description: str, inputs: dict | None = None) -> str:
    """Enhanced single agent runner with skill context."""
    from skills import get_skill_context
    
    skill_context = get_skill_context(agent_name)
    
    _AGENTS = {
        "planner": lambda: Agent(
            role="AI Research Specialist with Literature Expertise",
            goal=(
                "Conduct comprehensive literature reviews, identify research gaps, "
                "and design evidence-based experimental plans."
            ),
            backstory=(
                f"{skill_context} You are a senior researcher with deep expertise in "
                "machine learning literature and experimental design."
            ),
            llm=_gemini("gemini/gemini-3.1-pro-preview", temperature=0.8),
            tools=_PLANNER_TOOLS,
            verbose=True,
        ),
        "reviewer": lambda: Agent(
            role="Principal Engineer & Code Safety Auditor",
            goal=(
                "Perform comprehensive code reviews with mathematical verification, "
                "VRAM safety analysis, and HPC compatibility checks."
            ),
            backstory=(
                f"You are a principal engineer with expertise in code review, "
                "mathematical verification, and HPC system safety."
            ),
            llm=_openai("openai/gpt-5.3-chat-latest", temperature=1.0),
            tools=[CalculatorTool()],
            verbose=True,
        ),
        "coder": lambda: Agent(
            role="Expert HPC Engineer & Code Generator",
            goal=(
                "Generate production-ready, optimized code for GPU clusters "
                "with proper error handling and performance optimization."
            ),
            backstory=(
                f"You are a staff engineer specializing in distributed training "
                "systems and HPC optimization techniques."
            ),
            llm=_anthropic("anthropic/claude-opus-4-6", temperature=0.15),
            tools=[PyLintTool()],
            verbose=True,
        ),
        "executor": lambda: Agent(
            role="NU Explorer HPC Cluster Operations Specialist",
            goal=(
                "Execute research code on Northeastern Explorer HPC cluster "
                "with proper resource allocation and job management."
            ),
            backstory=(
                f"You are an HPC sysadmin with specific expertise in NU Explorer "
                "operations, SLURM workload management, and GPU cluster administration."
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


# Skill validation utility
if __name__ == "__main__":
    from skills import validate_skills
    
    validation = validate_skills()
    print("Enhanced Research Crew - Skill Validation:")
    for agent, valid in validation.items():
        status = "✅" if valid else "❌"
        print(f"  {status} {agent.title()} Agent")
    
    if all(validation.values()):
        print("\n🚀 All agent skills are properly configured!")
        print("Enhanced Research Crew is ready for specialized operations.")
    else:
        print("\n⚠️  Some agent skills are missing or invalid.")
        print("Please check skill file locations and permissions.")