"""
JUnit 5 test generator.

Provides two strategies:
1. **Template-based** – constructs tests using simple heuristics (no LLM needed).
2. **LLM-based** – uses :class:`~src.llm_client.client.LLMClient` to produce
   richer test suites.

The generated test source is returned as a plain Java string.  The pipeline can
then compile and run it using the standard executor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MethodSignature:
    name: str
    return_type: str
    params: List[str]
    is_static: bool


def _parse_public_methods(source: str) -> List[MethodSignature]:
    """Very lightweight Java method signature parser (good enough for simple classes)."""
    pattern = re.compile(
        r"\b(?P<static>static\s+)?(?P<ret>[\w<>\[\]]+)\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)",
        re.MULTILINE,
    )
    # Common non-method identifiers to skip
    _SKIP = {
        "if", "while", "for", "switch", "catch", "class", "interface", "new",
        "return", "throw", "assert", "synchronized", "instanceof",
    }
    methods: List[MethodSignature] = []
    for m in pattern.finditer(source):
        name = m.group("name")
        ret = m.group("ret")
        # Skip Java keywords and constructor-call patterns (e.g. `new SomeException(...)`)
        if name in _SKIP or ret in _SKIP:
            continue
        # Skip names that look like exception/error class names when ret is missing context
        if name[0].isupper() and ret == "new":
            continue
        params = [p.strip() for p in m.group("params").split(",") if p.strip()]
        methods.append(
            MethodSignature(
                name=name,
                return_type=ret,
                params=params,
                is_static=bool(m.group("static")),
            )
        )
    return methods


def _default_value(java_type: str) -> str:
    """Return a sensible literal for a given Java type."""
    mapping = {
        "int": "0",
        "long": "0L",
        "double": "0.0",
        "float": "0.0f",
        "boolean": "false",
        "char": "'a'",
        "byte": "0",
        "short": "0",
        "String": '""',
    }
    t = java_type.split("<")[0].strip()  # strip generics
    return mapping.get(t, "null")


def _extract_class_name(source: str) -> str:
    # Strip comments before searching to avoid matching "class" inside them.
    stripped = re.sub(r"//[^\n]*", "", source)
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)
    m = re.search(r"\bpublic\s+class\s+(\w+)", stripped)
    if m:
        return m.group(1)
    m = re.search(r"\bclass\s+(\w+)", stripped)
    return m.group(1) if m else "Main"


# ── template-based generator ──────────────────────────────────────────────────

def generate_template_tests(source_code: str) -> str:
    """
    Generate a basic JUnit 5 test class from *source_code* without an LLM.
    """
    class_name = _extract_class_name(source_code)
    methods = _parse_public_methods(source_code)

    test_methods: List[str] = []
    for method in methods:
        if method.name in {"main", class_name}:
            continue

        args = ", ".join(_default_value(p.split()[0] if " " in p else p) for p in method.params)
        invocation = (
            f"{class_name}.{method.name}({args})"
            if method.is_static
            else f"new {class_name}().{method.name}({args})"
        )

        if method.return_type in ("void", "Void"):
            assertion = f"        assertDoesNotThrow(() -> {invocation});"
        elif method.return_type == "boolean":
            assertion = f"        // adjust the expected value as needed\n        assertNotNull({invocation});"
        else:
            assertion = f"        assertNotNull({invocation});"

        test_methods.append(
            f"    @Test\n"
            f"    void test_{method.name}() {{\n"
            f"{assertion}\n"
            f"    }}"
        )

    if not test_methods:
        test_methods.append(
            f"    @Test\n"
            f"    void testPlaceholder() {{\n"
            f"        // TODO: add test cases for {class_name}\n"
            f"        assertTrue(true);\n"
            f"    }}"
        )

    body = "\n\n".join(test_methods)
    return (
        f"import org.junit.jupiter.api.Test;\n"
        f"import static org.junit.jupiter.api.Assertions.*;\n\n"
        f"class {class_name}Test {{\n\n"
        f"{body}\n"
        f"}}\n"
    )


# ── LLM-based generator ───────────────────────────────────────────────────────

def generate_llm_tests(
    source_code: str,
    llm_client,  # src.llm_client.client.LLMClient
) -> str:
    """
    Use *llm_client* to generate a richer JUnit 5 test class.
    Falls back to the template strategy when the LLM is unavailable.
    """
    class_name = _extract_class_name(source_code)
    if not llm_client.available:
        return generate_template_tests(source_code)
    return llm_client.generate_tests(source_code, class_name)


# ── unified entry point ───────────────────────────────────────────────────────

def generate_tests(
    source_code: str,
    llm_client: Optional[object] = None,
    *,
    use_llm: bool = True,
) -> str:
    """
    Generate a JUnit 5 test class for *source_code*.

    If *llm_client* is provided and ``use_llm`` is ``True``, the LLM strategy
    is used; otherwise the template strategy is used.
    """
    if use_llm and llm_client is not None:
        return generate_llm_tests(source_code, llm_client)
    return generate_template_tests(source_code)
