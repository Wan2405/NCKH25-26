"""LLM Client - Communicates with OpenAI-compatible APIs for code analysis."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import httpx


@dataclass
class LLMConfig:
    """Configuration for the LLM API."""

    api_key: str = ""
    api_base: str = "https://api.openai.com/v1"
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.2
    max_tokens: int = 2048
    timeout: int = 60

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create config from environment variables."""
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            api_base=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        )


@dataclass
class LLMResponse:
    """Response from the LLM API."""

    success: bool
    content: str = ""
    error: str = ""


class LLMClient:
    """Client for OpenAI-compatible chat completion APIs."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.from_env()

    async def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'.

        Returns:
            An LLMResponse with the assistant's reply.
        """
        if not self.config.api_key:
            return LLMResponse(
                success=False,
                error="API key not configured. Set OPENAI_API_KEY environment variable.",
            )

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        url = f"{self.config.api_base}/chat/completions"

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return LLMResponse(success=True, content=content)
            except httpx.HTTPStatusError as exc:
                return LLMResponse(
                    success=False,
                    error=f"HTTP {exc.response.status_code}: {exc.response.text[:500]}",
                )
            except httpx.RequestError as exc:
                return LLMResponse(
                    success=False,
                    error=f"Request failed: {exc}",
                )
            except (KeyError, IndexError, json.JSONDecodeError) as exc:
                return LLMResponse(
                    success=False,
                    error=f"Failed to parse response: {exc}",
                )

    async def analyze_code(self, source_code: str, error_output: str) -> LLMResponse:
        """Ask the LLM to analyze Java code and its errors.

        Returns an LLMResponse whose content is a JSON object with keys:
        - bugs: list of identified bugs
        - fixes: suggested fixes
        - fixed_code: corrected source code
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert Java developer. Analyze the given Java "
                    "source code and error output, then provide a JSON response "
                    "with the following structure:\n"
                    '{"bugs": [{"description": "...", "line": N, "severity": "high|medium|low"}], '
                    '"fixes": [{"description": "...", "line": N}], '
                    '"fixed_code": "...corrected Java source code..."}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Java source code:\n```java\n{source_code}\n```\n\n"
                    f"Error output:\n```\n{error_output}\n```"
                ),
            },
        ]
        return await self.chat(messages)

    async def generate_tests(self, source_code: str) -> LLMResponse:
        """Ask the LLM to generate test cases for Java code.

        Returns an LLMResponse whose content is JUnit 5 test source code.
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert Java developer. Generate comprehensive "
                    "JUnit 5 test cases for the given Java source code. "
                    "Include edge cases. Return only the Java test class code."
                ),
            },
            {
                "role": "user",
                "content": f"Generate tests for:\n```java\n{source_code}\n```",
            },
        ]
        return await self.chat(messages)

    async def suggest_fix(self, source_code: str, bug_description: str) -> LLMResponse:
        """Ask the LLM to suggest a fix for a specific bug.

        Returns an LLMResponse with the corrected source code.
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert Java developer. Fix the described bug "
                    "in the given Java source code. Return only the corrected "
                    "Java source code without explanation."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Bug: {bug_description}\n\n"
                    f"Source code:\n```java\n{source_code}\n```"
                ),
            },
        ]
        return await self.chat(messages)
