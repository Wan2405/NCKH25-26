"""
LLM CLIENT
==========
Interacts with a locally running Ollama instance (Llama 3.1 by default)
to generate Java code fixes.

No web framework or external service is required; Ollama must be running
locally on the machine that runs the pipeline.
"""

from __future__ import annotations

import json
import logging
import time

import requests

from llm.code_sanitizer import sanitize_java_code

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Sends prompts to Ollama and parses the JSON response.

    Args:
        base_url:    Ollama API base URL (default: ``http://localhost:11434``).
        model:       Model tag to use (default: ``llama3.1``).
        max_retries: Number of retry attempts on transient errors.
    """

    _DEFAULT_BASE_URL = "http://localhost:11434"
    _DEFAULT_MODEL = "llama3.1"

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        model: str = _DEFAULT_MODEL,
        max_retries: int = 3,
    ) -> None:
        self.generate_url = base_url.rstrip("/") + "/api/generate"
        self.model = model
        self.max_retries = max_retries

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def generate_fix(
        self,
        student_code: str,
        error_analysis: dict,
        problem_description: str = "",
    ) -> dict:
        """
        Ask the LLM to produce a corrected version of *student_code*.

        Returns:
            A dict with at least ``fixed_code`` and ``explanation`` keys.
            Returns ``{"fixed_code": "", "explanation": "LLM unavailable"}``
            if all retry attempts fail.
        """
        prompt = self._build_prompt(student_code, error_analysis, problem_description)

        for attempt in range(1, self.max_retries + 1):
            backoff = 2 ** (attempt - 1)
            try:
                logger.info(
                    "LLM generate_fix attempt %d/%d", attempt, self.max_retries
                )
                response = requests.post(
                    self.generate_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 1500},
                    },
                    timeout=120,
                )
                response.raise_for_status()
                payload = response.json()
                parsed = json.loads(payload.get("response", "{}"))
                if parsed.get("fixed_code", "").strip():
                    parsed["fixed_code"] = sanitize_java_code(
                        parsed["fixed_code"]
                    )
                    return parsed
                logger.warning(
                    "LLM returned empty fixed_code, retrying in %ds", backoff
                )
            except requests.ConnectionError:
                logger.warning("Ollama not reachable, retry in %ds", backoff)
            except requests.Timeout:
                logger.warning("Ollama request timed out, retry in %ds", backoff)
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Bad LLM response: %s, retry in %ds", exc, backoff)
            except Exception as exc:
                logger.error("Unexpected LLM error: %s", exc)
            time.sleep(backoff)

        return {"fixed_code": "", "explanation": "LLM unavailable after retries"}

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_prompt(
        self, code: str, error_analysis: dict, problem_description: str
    ) -> str:
        loai_loi = error_analysis.get("loai_loi", "Unknown")
        nguyen_nhan = error_analysis.get("nguyen_nhan", "Unknown")
        chi_tiet = error_analysis.get("chi_tiet", "")
        if isinstance(chi_tiet, list):
            chi_tiet = "\n".join(chi_tiet)

        code_snippet = code if len(code) <= 3000 else code[:3000]

        return (
            "You are a Java expert. A student's code has a bug. Fix it.\n\n"
            f"PROBLEM:\n{problem_description or 'Java exercise'}\n\n"
            f"STUDENT CODE:\n{code_snippet}\n\n"
            f"ERROR TYPE: {loai_loi}\n"
            f"REASON: {nguyen_nhan}\n"
            f"DETAILS: {str(chi_tiet)[:500]}\n\n"
            "IMPORTANT: Return the complete fixed Java source code. "
            "Do NOT wrap the code in markdown fences (no ```java). "
            "Do NOT change the public class name.\n\n"
            'Return JSON only: {"fixed_code": "...", "explanation": "...", "reasoning": "..."}'
        )
