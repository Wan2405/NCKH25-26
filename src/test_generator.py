"""Test Generator - Creates JUnit-style test cases for Java code."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TestCase:
    """A single test case for a Java method."""

    name: str
    input_value: str
    expected_output: str
    description: str = ""


@dataclass
class TestSuite:
    """A collection of test cases wrapped in JUnit source code."""

    class_name: str
    test_cases: list[TestCase] = field(default_factory=list)
    source_code: str = ""


def _extract_main_method(source_code: str) -> bool:
    """Check if the source code contains a main method."""
    return bool(re.search(r"public\s+static\s+void\s+main\s*\(", source_code))


def _extract_methods(source_code: str) -> list[dict[str, str]]:
    """Extract public method signatures from Java source code.

    Returns list of dicts with keys: return_type, name, params.
    """
    pattern = re.compile(
        r"public\s+(?:static\s+)?(?P<return_type>\w+)\s+(?P<name>\w+)"
        r"\s*\((?P<params>[^)]*)\)",
    )
    methods = []
    for m in pattern.finditer(source_code):
        name = m.group("name")
        if name == "main":
            continue
        methods.append(
            {
                "return_type": m.group("return_type"),
                "name": name,
                "params": m.group("params").strip(),
            }
        )
    return methods


def _extract_class_name(source_code: str) -> str:
    """Extract the public class name."""
    m = re.search(r"\bpublic\s+class\s+(\w+)", source_code)
    if m:
        return m.group(1)
    m = re.search(r"\bclass\s+(\w+)", source_code)
    return m.group(1) if m else "Unknown"


# --------------- Built-in heuristic test values ---------------

_TEST_VALUES: dict[str, list[str]] = {
    "int": ["0", "1", "-1", "100", "Integer.MAX_VALUE"],
    "long": ["0L", "1L", "-1L", "100L"],
    "double": ["0.0", "1.0", "-1.0", "3.14"],
    "float": ["0.0f", "1.0f", "-1.0f"],
    "String": ['""', '"hello"', '"a"', '"Hello World"'],
    "boolean": ["true", "false"],
    "char": ["'a'", "'z'", "'0'"],
    "int[]": ["new int[]{}", "new int[]{1}", "new int[]{1,2,3}"],
    "String[]": ['new String[]{}', 'new String[]{"a","b"}'],
}


def _default_values_for(param_type: str) -> list[str]:
    """Return a list of sample values for a Java type."""
    return _TEST_VALUES.get(param_type.strip(), ['"test"'])


def generate_method_tests(
    source_code: str,
    class_name: str | None = None,
) -> TestSuite:
    """Generate JUnit 5 test source code for public methods in *source_code*.

    The generated tests call each method with a variety of heuristic inputs
    and simply assert that the method does not throw an exception (smoke
    tests).  More specific assertions can be added manually or via LLM.
    """
    if class_name is None:
        class_name = _extract_class_name(source_code)

    methods = _extract_methods(source_code)
    test_class_name = f"{class_name}Test"
    test_cases: list[TestCase] = []
    test_methods_src: list[str] = []

    for method in methods:
        params_str = method["params"]
        param_types = []
        if params_str:
            for p in params_str.split(","):
                parts = p.strip().split()
                if parts:
                    param_types.append(parts[0])

        # Build argument combinations
        arg_lists: list[list[str]] = []
        for pt in param_types:
            arg_lists.append(_default_values_for(pt))

        # Generate one test per first-value combination (keep suite small)
        if not arg_lists:
            args_str = ""
            tc = TestCase(
                name=f"test_{method['name']}_noArgs",
                input_value="(no arguments)",
                expected_output="no exception",
                description=f"Smoke test for {method['name']}()",
            )
            test_cases.append(tc)
            is_static = "static" in source_code.split(method["name"])[0].split("\n")[-1]
            call = (
                f"{class_name}.{method['name']}()"
                if is_static
                else f"new {class_name}().{method['name']}()"
            )
            test_methods_src.append(
                f"    @Test\n"
                f"    void test_{method['name']}_noArgs() {{\n"
                f"        assertDoesNotThrow(() -> {call});\n"
                f"    }}\n"
            )
        else:
            for i, pt in enumerate(param_types):
                vals = _default_values_for(pt)
                first_val = vals[0] if vals else '"test"'
                # Build args using first value for each param
                args = []
                for j, pt2 in enumerate(param_types):
                    v = _default_values_for(pt2)
                    if j == i and len(v) > 1:
                        args.append(v[1])  # vary the i-th parameter
                    else:
                        args.append(v[0] if v else '"test"')
                args_combined = ", ".join(args)
                tc = TestCase(
                    name=f"test_{method['name']}_case{i}",
                    input_value=args_combined,
                    expected_output="no exception",
                    description=f"Smoke test for {method['name']}({args_combined})",
                )
                test_cases.append(tc)
                is_static = "static" in source_code.split(method["name"])[0].split("\n")[-1]
                call = (
                    f"{class_name}.{method['name']}({args_combined})"
                    if is_static
                    else f"new {class_name}().{method['name']}({args_combined})"
                )
                test_methods_src.append(
                    f"    @Test\n"
                    f"    void test_{method['name']}_case{i}() {{\n"
                    f"        assertDoesNotThrow(() -> {call});\n"
                    f"    }}\n"
                )

    test_source = (
        "import org.junit.jupiter.api.Test;\n"
        "import static org.junit.jupiter.api.Assertions.*;\n\n"
        f"class {test_class_name} {{\n\n"
        + "\n".join(test_methods_src)
        + "}\n"
    )

    return TestSuite(
        class_name=test_class_name,
        test_cases=test_cases,
        source_code=test_source,
    )


def generate_io_tests(
    source_code: str,
    test_cases_data: list[dict[str, str]],
) -> list[TestCase]:
    """Create TestCase objects for main-method programs that use stdin/stdout.

    Args:
        source_code: The Java source.
        test_cases_data: List of dicts with 'input' and 'expected_output'.

    Returns:
        List of TestCase instances.
    """
    cases: list[TestCase] = []
    for i, tc in enumerate(test_cases_data):
        cases.append(
            TestCase(
                name=f"io_test_{i}",
                input_value=tc.get("input", ""),
                expected_output=tc.get("expected_output", ""),
                description=tc.get("description", f"I/O test case {i}"),
            )
        )
    return cases
