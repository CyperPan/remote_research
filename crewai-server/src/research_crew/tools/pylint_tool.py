"""PyLintTool — runs pylint on generated code before it reaches the Reviewer."""
import os
import subprocess
import tempfile
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class PyLintInput(BaseModel):
    code: str = Field(..., description="Python source code to lint")


class PyLintTool(BaseTool):
    name: str = "pylint_checker"
    description: str = (
        "Run pylint on a Python code snippet and return the full lint report "
        "(errors, warnings, score). Use this BEFORE submitting code to the Reviewer "
        "to catch syntax errors, undefined variables, and style issues locally."
    )
    args_schema: type[BaseModel] = PyLintInput

    def _run(self, code: str) -> str:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            tmp_path = f.name
        try:
            result = subprocess.run(
                ["pylint", "--output-format=text", "--score=yes",
                 "--disable=C0114,C0115,C0116",  # suppress missing-docstring noise
                 tmp_path],
                capture_output=True, text=True, timeout=30,
            )
            output = (result.stdout + result.stderr).strip()
            return output if output else "pylint: no issues found (10/10)"
        except FileNotFoundError:
            return "pylint not found in PATH — skipping lint check"
        except subprocess.TimeoutExpired:
            return "pylint timed out after 30s"
        finally:
            os.unlink(tmp_path)
