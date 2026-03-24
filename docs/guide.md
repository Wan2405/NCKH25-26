# NCKH25-26 – Internal Project Guide

This document explains the project in a way that a new reader (lecturer/supervisor, students from other teams, or new contributors) can understand without prior context.

---

## 1. Project Overview

### What is this project?

**NCKH25-26** is an **AI-assisted Java debugging pipeline**.

Input:
- A Maven Java project (source code + tests)
- A Java file that currently fails to compile or fails tests

Output:
- A revised version of the Java code produced by the AI loop
- A round-by-round history file showing what happened in each attempt

### What problem does it solve?

When students write Java code, they often face repeated cycles:
1. Run code/tests
2. Read long error logs
3. Guess the cause
4. Edit code
5. Run again

This project automates that loop. It can:
- run compile/test in a controlled environment,
- classify failure type,
- ask an AI model for a fix,
- re-run tests,
- repeat until pass or max rounds.

### Real-world use case (simple and concrete)

A student submits:
- `Solution.java` with logic bug (`a - b` instead of `a + b`)
- `SolutionTest.java` containing expected outputs

The system:
1. Runs `mvn clean test` in Docker
2. Detects test failure from Maven/JUnit logs
3. Sends code + error context to local LLM (Llama 3.1 via Ollama)
4. Replaces code with suggested fix
5. Re-tests
6. Stops when tests pass

Result: student and instructor can see both the final code and debugging history.

---

## 2. Context & Background

### Why was this project built?

The project was built for an educational scenario where many Java solutions need iterative debugging support.

Main motivations:
- **Reduce repetitive manual debugging effort** for students.
- **Provide structured debugging traces** for instructors.
- **Keep execution consistent** across machines by using Docker.
- **Use local AI inference** (Ollama) to avoid dependence on external cloud APIs.

### What scenario led to it?

Typical classroom pain points:
- Students cannot interpret compile/runtime/test logs quickly.
- Instructors spend time repeating similar feedback.
- Different local environments (JDK/Maven versions) create inconsistent results.

This project addresses those points with one repeatable feedback loop.

---

## 3. Technology Stack

Below is the stack and why each part is used.

- **Python 3**
  - Used to orchestrate the whole pipeline (CLI, loop control, module integration).
  - Chosen because it is fast to build automation workflows and integrates well with APIs.

- **Java 17**
  - Target language of student code being debugged.
  - The sample workspace is configured for Java 17 compatibility.

- **Maven**
  - Standard Java build/test tool in this project.
  - Used to compile code and run tests (`mvn clean test --batch-mode`).

- **JUnit 5 (Jupiter)**
  - Test framework used in workspace test files.
  - Provides objective pass/fail signal for each debugging round.

- **Docker + Python Docker SDK (`docker` package)**
  - Runs Maven tests in an isolated container (`nckh-build-env`).
  - Prevents host-machine dependency mismatch and improves reproducibility.

- **Ollama (local model runtime)**
  - Hosts local LLM inference endpoint (`http://localhost:11434`).
  - Allows the project to call a local AI model without cloud dependency.

- **Llama 3.1 model (via Ollama)**
  - Generates candidate fixed Java code from code + error context.
  - Used in each failed round to propose the next code revision.

- **Requests (Python HTTP client)**
  - Sends HTTP requests from `llm/llm_client.py` to Ollama API.

- **Regex + custom log processing modules**
  - Extract class name, parse Maven/JUnit logs, and classify error categories.
  - Converts raw logs into structured data for AI prompts and reporting.

---

## 4. System Architecture

### High-level flow

```text
run_feedback_loop.py (CLI entry)
        |
        v
LoopOrchestrator (core loop controller)
        |
        +--> DockerManager: run mvn clean test in Docker
        |
        +--> LogProcessor: parse raw logs into structured result
        |
        +--> ErrorClassifier: determine failure type/cause
        |
        +--> LLMClient: request fixed Java code from Ollama
        |
        +--> repeat until PASSED or max rounds
```

### Main components and interactions

1. **`run_feedback_loop.py`**
   - Parses CLI arguments (`--workspace`, `--max-rounds`)
   - Finds first Java source file under `src/main/java`
   - Creates all service objects and starts orchestration

2. **`core/loop_orchestrator.py`**
   - Central controller of round-by-round execution
   - Writes current code to workspace
   - Coordinates test run, log parsing, classification, and AI fix generation
   - Saves round history JSON in `auto_grader/output/auto_fix_history/`

3. **`core/docker_manager.py`**
   - Creates container from image `nckh-build-env`
   - Mounts workspace and runs `mvn clean test --batch-mode`
   - Returns combined output logs + exit code

4. **`execution/log_processor.py` and `auto_grader/modules/log_processor.py`**
   - Convert raw text logs into structured fields (error type, details, test summary)

5. **`execution/error_classifier.py` and `auto_grader/modules/error_classifier.py`**
   - Assign failure category (e.g., compile error, test failed, passed)
   - Provide reason/context used in next AI prompt

6. **`llm/llm_client.py` + `llm/code_sanitizer.py`**
   - Build prompt and call Ollama API
   - Parse returned JSON and sanitize generated Java code before reuse

---

## 5. Key Features / Use Cases

### Core features

- **Automated feedback loop**
  - Re-runs compile/test after each AI-generated fix.

- **Containerized execution**
  - All Java test execution runs in Docker for consistency.

- **Structured error understanding**
  - Raw Maven/JUnit output is transformed into machine-usable error data.

- **AI-based code repair suggestion**
  - Local LLM proposes complete revised Java source code.

- **Traceable history output**
  - Each run stores a JSON history with round status and timestamps.

### Typical use cases

- Student wants quick iteration on a failing Java solution.
- Instructor wants to demonstrate automated debugging steps in class.
- Team wants to compare “before/after” repair rounds for analysis.

---

## 6. How to Run the Project

This section assumes a beginner setup.

### Step 1: Prepare tools

Install and verify:
- Docker Desktop / Docker Engine
- Python 3
- Ollama

Then pull model:

```bash
ollama pull llama3.1
```

Start Ollama server (if not already running):

```bash
ollama serve
```

### Step 2: Install Python dependencies

From repository root:

```bash
pip install -r requirements.txt
```

### Step 3: Build the Docker image used by the pipeline

From repository root:

```bash
docker build -t nckh-build-env .
```

### Step 4: Prepare workspace structure

Expected minimum structure:

```text
workspace/
  pom.xml
  src/main/java/com/example/Solution.java
  src/test/java/com/example/SolutionTest.java
```

### Step 5: Run the feedback loop

```bash
python run_feedback_loop.py --workspace ./workspace --max-rounds 3
```

Parameters:
- `--workspace` (required): path to Maven workspace
- `--max-rounds` (optional): maximum fix attempts (default is 3)

### Step 6: Check outputs

- Terminal summary shows pass/fail and per-round status.
- History JSON is saved under:
  - `auto_grader/output/auto_fix_history/`

---

## 7. Example Workflow

Below is a concrete start-to-finish scenario.

1. User writes `Solution.java` with wrong logic.
2. User writes/keeps JUnit tests in `SolutionTest.java`.
3. User runs:
   ```bash
   python run_feedback_loop.py --workspace ./workspace --max-rounds 3
   ```
4. Round 1:
   - Docker runs Maven tests.
   - Tests fail.
   - System classifies failure and asks LLM for a fix.
5. Round 2:
   - Revised code is tested again.
   - If all tests pass, loop ends with `PASSED`.
6. System prints summary and stores history JSON.

What the user sees:
- Immediate terminal feedback for each round
- Final pass/fail result
- Persisted round history for later review by instructor/supervisor

---

## 8. Notes / Limitations

- **Single-source discovery behavior**
  - Current entry flow picks the first `.java` file found under `src/main/java`.
  - Projects needing multi-file targeted repair may require orchestration extension.

- **Model availability dependency**
  - Ollama service and the selected model (`llama3.1`) must be available locally.
  - If Ollama is down or unreachable, AI fix generation fails after retries.

- **Quality of AI-generated fix is not guaranteed**
  - The loop is bounded by `--max-rounds`.
  - Some failures may remain unresolved within allowed attempts.

- **Docker requirement for intended reproducibility**
  - The design expects containerized execution; missing Docker setup blocks normal flow.

- **Test coverage limits repair quality**
  - The system can only confirm correctness against provided tests.
  - Weak/incomplete tests can allow logically incorrect code to appear as “passed”.

