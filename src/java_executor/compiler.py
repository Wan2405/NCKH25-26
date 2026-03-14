"""
Java compiler wrapper.

Writes the given Java source code to a temporary file inside ``workspace_dir``,
compiles it with ``javac``, and returns structured output that includes
compilation success/failure and any diagnostics.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import config


@dataclass
class CompilationDiagnostic:
    """One compiler diagnostic (error / warning)."""

    line: int
    column: int
    kind: str          # "error" | "warning" | "note"
    message: str
    source_excerpt: str = ""


@dataclass
class CompilationResult:
    success: bool
    class_name: str
    source_file: str
    work_dir: str
    diagnostics: List[CompilationDiagnostic] = field(default_factory=list)
    raw_output: str = ""

    @property
    def errors(self) -> List[CompilationDiagnostic]:
        return [d for d in self.diagnostics if d.kind == "error"]

    @property
    def warnings(self) -> List[CompilationDiagnostic]:
        return [d for d in self.diagnostics if d.kind == "warning"]


# ── helpers ──────────────────────────────────────────────────────────────────

_DIAG_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+): (?P<kind>error|warning|note): (?P<msg>.+)$"
)


def _parse_diagnostics(raw: str) -> List[CompilationDiagnostic]:
    """Parse javac stderr into a list of :class:`CompilationDiagnostic`."""
    diags: List[CompilationDiagnostic] = []
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        m = _DIAG_RE.match(lines[i])
        if m:
            excerpt = ""
            column = 0
            # next line may be the source excerpt, the one after the caret
            if i + 1 < len(lines):
                excerpt = lines[i + 1]
                if i + 2 < len(lines) and "^" in lines[i + 2]:
                    column = lines[i + 2].index("^") + 1
                    i += 2
                else:
                    i += 1
            diags.append(
                CompilationDiagnostic(
                    line=int(m.group("line")),
                    column=column,
                    kind=m.group("kind"),
                    message=m.group("msg").strip(),
                    source_excerpt=excerpt.strip(),
                )
            )
        i += 1
    return diags


def _extract_class_name(source: str) -> str:
    """Return the first *public class* name found in the source, or 'Main'."""
    # Strip single-line comments before searching so we don't match inside comments.
    stripped = re.sub(r"//[^\n]*", "", source)
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)

    m = re.search(r"\bpublic\s+class\s+(\w+)", stripped)
    if m:
        return m.group(1)
    m = re.search(r"\bclass\s+(\w+)", stripped)
    if m:
        return m.group(1)
    return "Main"


# ── public API ────────────────────────────────────────────────────────────────

def compile_java(
    source_code: str,
    *,
    workspace_dir: str | None = None,
    javac_path: str | None = None,
) -> CompilationResult:
    """
    Compile *source_code* and return a :class:`CompilationResult`.

    A fresh subdirectory inside *workspace_dir* is created for each call so
    concurrent compilations do not interfere with each other.
    """
    workspace_dir = workspace_dir or config.WORKSPACE_DIR
    javac_path = javac_path or config.JAVAC_PATH
    class_name = _extract_class_name(source_code)

    work_dir = tempfile.mkdtemp(prefix="javac_", dir=workspace_dir)
    source_file = os.path.join(work_dir, f"{class_name}.java")

    Path(source_file).write_text(source_code, encoding="utf-8")

    try:
        proc = subprocess.run(
            [javac_path, source_file],
            capture_output=True,
            text=True,
            timeout=config.EXECUTION_TIMEOUT,
        )
    except FileNotFoundError:
        return CompilationResult(
            success=False,
            class_name=class_name,
            source_file=source_file,
            work_dir=work_dir,
            raw_output="javac not found. Ensure the JDK is installed and JAVAC_PATH is set.",
        )
    except subprocess.TimeoutExpired:
        return CompilationResult(
            success=False,
            class_name=class_name,
            source_file=source_file,
            work_dir=work_dir,
            raw_output="Compilation timed out.",
        )

    raw = (proc.stdout + proc.stderr).strip()
    diagnostics = _parse_diagnostics(raw)

    return CompilationResult(
        success=proc.returncode == 0,
        class_name=class_name,
        source_file=source_file,
        work_dir=work_dir,
        diagnostics=diagnostics,
        raw_output=raw,
    )
