"""CalculatorTool — safe math evaluator for VRAM/FLOPs estimation in code review."""
import math
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class CalcInput(BaseModel):
    expression: str = Field(
        ...,
        description=(
            "A Python math expression to evaluate precisely. "
            "Examples: '7e9 * 2 / 1024**3' for 7B fp16 params in GB, "
            "'(70e9 * 4 + 70e9 * 12) / 1024**3' for optimizer state."
        ),
    )


class CalculatorTool(BaseTool):
    name: str = "calculator"
    description: str = (
        "Evaluate a mathematical expression and return the exact numeric result. "
        "Use for VRAM calculations (params × bytes / 1024³), FLOPs estimates, "
        "batch memory footprints, and any arithmetic needed during code review. "
        "Always use this instead of mental arithmetic to avoid LLM math errors."
    )
    args_schema: type[BaseModel] = CalcInput

    def _run(self, expression: str) -> str:
        safe_ns = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        safe_ns.update({"__builtins__": {}, "e": math.e, "pi": math.pi})
        try:
            result = eval(  # noqa: S307 – expression is sandboxed
                compile(expression, "<calc>", "eval"),
                {"__builtins__": {}},
                safe_ns,
            )
            if isinstance(result, float):
                return f"{expression} = {result:.6g}"
            return f"{expression} = {result}"
        except Exception as ex:
            return f"Error evaluating '{expression}': {ex}"
