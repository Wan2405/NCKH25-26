package com.nckh.model;

import java.util.List;

/**
 * Captures the outcome of one build-and-test cycle executed inside the Docker container.
 * Produced by {@link com.nckh.execution.BuildEngine} and evaluated by
 * {@link com.nckh.core.LoopOrchestrator} to decide the next step.
 */
public class ExecutionResult {

    public enum Status {
        /** Maven build succeeded and all JUnit tests passed. */
        SUCCESS,
        /** Maven compilation failed. */
        COMPILE_FAILURE,
        /** Compilation succeeded but one or more JUnit tests failed. */
        TEST_FAILURE,
        /** Execution timed-out or hit a Docker resource limit. */
        TIMEOUT,
        /** Unexpected internal error (e.g., Docker API failure). */
        INTERNAL_ERROR
    }

    private Status status;
    private String stdout;
    private String stderr;
    private int totalTests;
    private int passedTests;
    private int failedTests;
    private List<ErrorReport> errors;
    private long durationMillis;

    public ExecutionResult() {}

    // ---- Convenience factory methods ----

    public static ExecutionResult success(String stdout, int total, long durationMillis) {
        ExecutionResult r = new ExecutionResult();
        r.status = Status.SUCCESS;
        r.stdout = stdout;
        r.totalTests = total;
        r.passedTests = total;
        r.failedTests = 0;
        r.durationMillis = durationMillis;
        return r;
    }

    public static ExecutionResult failure(Status status, String stdout, String stderr,
                                          List<ErrorReport> errors, int total, int passed, long durationMillis) {
        ExecutionResult r = new ExecutionResult();
        r.status = status;
        r.stdout = stdout;
        r.stderr = stderr;
        r.errors = errors;
        r.totalTests = total;
        r.passedTests = passed;
        r.failedTests = total - passed;
        r.durationMillis = durationMillis;
        return r;
    }

    // ---- Helpers ----

    public boolean isSuccess() { return status == Status.SUCCESS; }
    public boolean isTerminal() { return status == Status.TIMEOUT || status == Status.INTERNAL_ERROR; }

    // ---- Getters & Setters ----

    public Status getStatus() { return status; }
    public void setStatus(Status status) { this.status = status; }

    public String getStdout() { return stdout; }
    public void setStdout(String stdout) { this.stdout = stdout; }

    public String getStderr() { return stderr; }
    public void setStderr(String stderr) { this.stderr = stderr; }

    public int getTotalTests() { return totalTests; }
    public void setTotalTests(int totalTests) { this.totalTests = totalTests; }

    public int getPassedTests() { return passedTests; }
    public void setPassedTests(int passedTests) { this.passedTests = passedTests; }

    public int getFailedTests() { return failedTests; }
    public void setFailedTests(int failedTests) { this.failedTests = failedTests; }

    public List<ErrorReport> getErrors() { return errors; }
    public void setErrors(List<ErrorReport> errors) { this.errors = errors; }

    public long getDurationMillis() { return durationMillis; }
    public void setDurationMillis(long durationMillis) { this.durationMillis = durationMillis; }

    @Override
    public String toString() {
        return String.format("ExecutionResult{status=%s, tests=%d/%d, duration=%dms}",
                status, passedTests, totalTests, durationMillis);
    }
}
