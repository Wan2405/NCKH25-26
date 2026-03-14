"""
Configuration for the Automated Java Testing & Debugging System.
Values can be overridden with environment variables.
"""
import os

# ─── LLM settings ────────────────────────────────────────────────────────────
LLM_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "60"))

# ─── Java toolchain ──────────────────────────────────────────────────────────
JAVAC_PATH: str = os.getenv("JAVAC_PATH", "javac")
JAVA_PATH: str = os.getenv("JAVA_PATH", "java")

# ─── Workspace ───────────────────────────────────────────────────────────────
# Temporary directory used to write, compile and run Java sources.
WORKSPACE_DIR: str = os.getenv("WORKSPACE_DIR", "workspace")

# ─── Pipeline settings ───────────────────────────────────────────────────────
# Maximum number of auto-fix iterations before giving up.
MAX_FIX_ITERATIONS: int = int(os.getenv("MAX_FIX_ITERATIONS", "3"))
# Execution timeout in seconds.
EXECUTION_TIMEOUT: int = int(os.getenv("EXECUTION_TIMEOUT", "15"))

# ─── API server ──────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
