"""
LLM client wrapper.

Provides a thin, mock-friendly abstraction over the OpenAI chat-completions
API.  When ``api_key`` is empty, the client falls back to a rule-based
placeholder so the rest of the system can still function without a live LLM.
"""
from __future__ import annotations

import config


class LLMClient:
    """Synchronous wrapper around the OpenAI chat-completions endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.api_key = api_key or config.LLM_API_KEY
        self.base_url = base_url or config.LLM_BASE_URL
        self.model = model or config.LLM_MODEL
        self.timeout = timeout or config.LLM_TIMEOUT
        self._client = None  # lazily initialised

    # ── internal helpers ──────────────────────────────────────────────────────

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI  # type: ignore
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=self.timeout,
                )
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"Failed to initialise OpenAI client: {exc}") from exc
        return self._client

    def _chat(self, system: str, user: str) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""

    @property
    def available(self) -> bool:
        """True when an API key is configured."""
        return bool(self.api_key)

    # ── public API ────────────────────────────────────────────────────────────

    def generate_tests(self, source_code: str, class_name: str) -> str:
        """
        Ask the LLM to generate a JUnit 5 test class for *source_code*.
        Returns the raw Java source of the test class.
        """
        if not self.available:
            return _stub_test(class_name)

        system = (
            "You are an expert Java developer. "
            "Generate a complete JUnit 5 test class for the given Java code. "
            "Use @Test, assertTrue, assertEquals, assertThrows as appropriate. "
            "Output ONLY the Java source code, no explanation."
        )
        user = f"Java class to test:\n```java\n{source_code}\n```"
        return self._chat(system, user)

    def fix_code(self, source_code: str, bug_description: str) -> str:
        """
        Ask the LLM to fix *source_code* given a textual *bug_description*.
        Returns the corrected Java source code.
        """
        if not self.available:
            return source_code  # no-op stub when no key is configured

        system = (
            "You are an expert Java developer and debugger. "
            "Given the buggy Java code and a bug description, return ONLY the corrected Java source code. "
            "Do not include any explanation or markdown fences."
        )
        user = (
            f"Buggy code:\n```java\n{source_code}\n```\n\n"
            f"Bug description:\n{bug_description}"
        )
        return self._chat(system, user)

    def explain_code(self, source_code: str) -> str:
        """Ask the LLM to explain what the Java code does."""
        if not self.available:
            return "LLM not configured. Set the OPENAI_API_KEY environment variable to enable AI explanations."

        system = "You are a helpful Java tutor. Explain the following Java code concisely."
        user = f"```java\n{source_code}\n```"
        return self._chat(system, user)


# ── stub helpers (used when no API key is configured) ─────────────────────────

def _stub_test(class_name: str) -> str:
    """Return a minimal JUnit 5 test stub when the LLM is unavailable."""
    return f"""\
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class {class_name}Test {{

    @Test
    void testPlaceholder() {{
        // TODO: add test cases for {class_name}
        assertTrue(true, "Replace this with real assertions.");
    }}
}}
"""
