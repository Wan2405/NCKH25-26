"""
Entry point for the Automated Java Testing & Debugging System.

Usage:
    # Start the REST API server
    python main.py serve

    # Run the pipeline on a Java file from the command line
    python main.py run <path-to-java-file>

    # Generate tests for a Java file
    python main.py test <path-to-java-file>
"""
from __future__ import annotations

import sys


def _usage() -> None:
    print(__doc__)
    sys.exit(1)


def cmd_serve(args: list[str]) -> None:
    import uvicorn
    import config
    uvicorn.run("api.app:app", host=config.API_HOST, port=config.API_PORT, reload=True)


def cmd_run(args: list[str]) -> None:
    if not args:
        print("Error: provide a path to a .java file.")
        _usage()

    path = args[0]
    with open(path, encoding="utf-8") as f:
        source = f.read()

    stdin_data = None
    if len(args) > 1:
        with open(args[1], encoding="utf-8") as f:
            stdin_data = f.read()

    from src.pipeline.pipeline import run_pipeline
    result = run_pipeline(source, stdin=stdin_data)

    print("=" * 60)
    print(result.summary())
    print("=" * 60)

    if result.fixed:
        print("\nFinal (fixed) code:")
        print(result.final_code)
    else:
        for rec in result.iterations:
            if rec.bug_report.has_bugs:
                print(f"\n[Iteration {rec.iteration}] Bugs found:")
                print(rec.bug_report.as_text())

    if result.generated_tests:
        print("\nGenerated JUnit 5 tests:")
        print(result.generated_tests)


def cmd_test(args: list[str]) -> None:
    if not args:
        print("Error: provide a path to a .java file.")
        _usage()

    path = args[0]
    with open(path, encoding="utf-8") as f:
        source = f.read()

    from src.test_generator.generator import generate_tests
    tests = generate_tests(source, use_llm=False)
    print(tests)


_COMMANDS = {
    "serve": cmd_serve,
    "run": cmd_run,
    "test": cmd_test,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in _COMMANDS:
        _usage()
    _COMMANDS[sys.argv[1]](sys.argv[2:])
