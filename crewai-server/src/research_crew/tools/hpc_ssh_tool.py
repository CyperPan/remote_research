"""Custom CrewAI tool: execute commands on HPC cluster via SSH (paramiko)."""
import os
import paramiko
from crewai.tools import BaseTool


class HPCSSHTool(BaseTool):
    name: str = "HPC SSH Executor"
    description: str = (
        "Execute shell commands or submit scripts on the remote HPC cluster via SSH. "
        "Input: a shell command string (e.g. 'sbatch job.sh' or 'python3 ~/exp/run.py'). "
        "Returns stdout + stderr. Use for running experiments, checking job queues, or "
        "fetching results from the HPC cluster."
    )

    def _run(self, command: str) -> str:
        host = os.getenv("HPC_HOST", "")
        user = os.getenv("HPC_USER", "zhiyuan")
        key_path = os.path.expanduser(os.getenv("HPC_KEY_PATH", "~/.ssh/id_ed25519"))

        if not host:
            return "Error: HPC_HOST is not configured in .env — skipping remote execution."

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(host, username=user, key_filename=key_path, timeout=30)
            _, stdout, stderr = client.exec_command(command, timeout=300)
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            client.close()
            return (out + ("\n[stderr]\n" + err if err else "")) or "(no output)"
        except Exception as exc:
            return f"SSH connection error: {exc}"
