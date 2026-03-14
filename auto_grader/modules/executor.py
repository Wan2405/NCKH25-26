"""
JAVA EXECUTOR
Pipeline: code -> save temp file -> compile (javac) -> run (Docker or local) -> return result
"""

import logging
import os
import re
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)


def extract_class_name(code):
    """Extract the public class name from Java source code."""
    match = re.search(r'public\s+class\s+(\w+)', code)
    if match:
        return match.group(1)
    match = re.search(r'class\s+(\w+)', code)
    if match:
        return match.group(1)
    return "Solution"


def _docker_available():
    """Return True if Docker daemon is reachable."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def _run_local(temp_dir, class_name):
    """Run compiled Java class locally."""
    try:
        result = subprocess.run(
            ["java", "-cp", temp_dir, class_name],
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace"
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Runtime timeout (10s)", "exit_code": -1}
    except Exception as e:
        logger.exception("Local run failed")
        return {"stdout": "", "stderr": str(e), "exit_code": -1}


def _run_in_docker(temp_dir, class_name):
    """
    Run compiled Java class inside a Docker sandbox.
    Falls back to local execution if Docker fails.
    """
    try:
        abs_temp_dir = os.path.abspath(temp_dir)
        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", "256m",
            "--cpus", "1.0",
            "--pids-limit", "50",
            "-v", "{}:/code:ro".format(abs_temp_dir),
            "openjdk:11-slim",
            "java", "-cp", "/code", class_name
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace"
        )

        # Exit code 125 means docker itself failed (e.g. image not found).
        # Fall back to local execution in that case.
        if result.returncode == 125:
            logger.warning(
                "Docker failed (exit 125), falling back to local execution. stderr: %s",
                result.stderr[:200]
            )
            return _run_local(temp_dir, class_name)

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Docker runtime timeout (30s)", "exit_code": -1}
    except Exception as e:
        logger.warning("Docker run failed, falling back to local: %s", e)
        return _run_local(temp_dir, class_name)


def execute(code):
    """
    Full execution pipeline:
      1. Extract the public class name from the code
      2. Save the code to a temporary file
      3. Compile with javac
      4. Run with java (inside Docker sandbox if Docker is available)
      5. Clean up the temporary directory
      6. Return the result

    Args:
        code (str): Java source code

    Returns:
        dict with keys:
            status        - 'compile_error' | 'runtime_error' | 'success' | 'timeout' | 'error'
            class_name    - detected Java class name
            compile_error - compiler stderr (non-empty on compile_error)
            stdout        - program stdout
            stderr        - program stderr / runtime error
            exit_code     - process exit code
            used_docker   - True if Docker sandbox was used
    """
    class_name = "Solution"
    temp_dir = None
    try:
        class_name = extract_class_name(code)
        temp_dir = tempfile.mkdtemp(prefix="autograde_")
        java_file = os.path.join(temp_dir, "{}.java".format(class_name))

        logger.info("Executing code for class '%s' in %s", class_name, temp_dir)

        with open(java_file, "w", encoding="utf-8") as f:
            f.write(code)

        # Compile
        compile_result = subprocess.run(
            ["javac", java_file],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=temp_dir,
            encoding="utf-8",
            errors="replace"
        )

        if compile_result.returncode != 0:
            logger.warning("Compile error for class '%s'", class_name)
            return {
                "status": "compile_error",
                "class_name": class_name,
                "compile_error": compile_result.stderr,
                "stdout": "",
                "stderr": compile_result.stderr,
                "exit_code": compile_result.returncode,
                "used_docker": False
            }

        logger.info("Compilation successful for class '%s'", class_name)

        # Run
        use_docker = _docker_available()
        if use_docker:
            logger.info("Running in Docker sandbox")
            run_result = _run_in_docker(temp_dir, class_name)
        else:
            logger.info("Docker not available, running locally")
            run_result = _run_local(temp_dir, class_name)

        status = "success" if run_result["exit_code"] == 0 else "runtime_error"

        return {
            "status": status,
            "class_name": class_name,
            "compile_error": "",
            "stdout": run_result["stdout"],
            "stderr": run_result["stderr"],
            "exit_code": run_result["exit_code"],
            "used_docker": use_docker
        }

    except subprocess.TimeoutExpired:
        logger.error("Execution timed out")
        return {
            "status": "timeout",
            "class_name": class_name,
            "compile_error": "Execution timed out",
            "stdout": "",
            "stderr": "Execution timed out",
            "exit_code": -1,
            "used_docker": False
        }
    except FileNotFoundError:
        logger.error("javac not found — Java is not installed")
        return {
            "status": "error",
            "class_name": class_name,
            "compile_error": "javac not found. Please install Java.",
            "stdout": "",
            "stderr": "javac not found. Please install Java.",
            "exit_code": -1,
            "used_docker": False
        }
    except Exception as e:
        logger.exception("Unexpected error during execution")
        return {
            "status": "error",
            "class_name": class_name,
            "compile_error": str(e),
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "used_docker": False
        }
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
