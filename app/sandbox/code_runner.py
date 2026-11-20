import sys
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Any

class CodeRunner:
    """Safely executes code snippets and captures standard output and errors."""

    @classmethod
    def run_python(cls, code: str, timeout_sec: int = 10) -> Dict[str, Any]:
        """Execute a Python snippet in an isolated subprocess with timeout."""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as temp:
            temp_path = Path(temp.name)
            temp.write(code)

        start_time = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, str(temp_path)],
                capture_output=True,
                text=True,
                timeout=timeout_sec
            )
            elapsed = round((time.time() - start_time) * 1000, 2)
            return {
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "elapsed_ms": elapsed
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout_sec} seconds.",
                "elapsed_ms": timeout_sec * 1000
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Runner exception: {str(e)}",
                "elapsed_ms": 0
            }
        finally:
            try:
                temp_path.unlink()
            except Exception:
                pass
