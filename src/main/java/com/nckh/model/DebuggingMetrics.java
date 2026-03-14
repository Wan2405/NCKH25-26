package com.nckh.model;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * Tracks research metrics across the entire debugging loop run.
 * Used by {@link com.nckh.core.LoopOrchestrator} to record per-iteration data and
 * produce a final summary compatible with the research evaluation criteria:
 * compile-success@1, pass-all-tests@k, mean time-per-iteration, error-type distribution.
 */
public class DebuggingMetrics {

    private final Instant startTime = Instant.now();
    private Instant endTime;

    private int totalIterations = 0;
    private int compileSuccessCount = 0;   // iterations where build succeeded
    private int passAllTestsIteration = -1; // first iteration where all tests passed (-1 = never)

    private final List<String> stopReasons = new ArrayList<>();
    private final List<Long> iterationDurationsMs = new ArrayList<>();
    private final List<String> errorTypesPerIteration = new ArrayList<>();

    // ---- Recording methods ----

    public void recordIteration(ExecutionResult result) {
        totalIterations++;
        iterationDurationsMs.add(result.getDurationMillis());

        if (result.getStatus() != ExecutionResult.Status.COMPILE_FAILURE) {
            compileSuccessCount++;
        }
        if (result.isSuccess() && passAllTestsIteration < 0) {
            passAllTestsIteration = totalIterations;
        }
        if (result.getErrors() != null && !result.getErrors().isEmpty()) {
            errorTypesPerIteration.add(result.getErrors().get(0).getType().name());
        } else {
            errorTypesPerIteration.add(result.getStatus().name());
        }
    }

    public void recordStop(String reason) {
        stopReasons.add(reason);
        if (endTime == null) {
            endTime = Instant.now();
        }
    }

    // ---- Derived metrics ----

    /** compile-success@1 – did the code compile on the very first attempt? */
    public boolean isCompileSuccessAt1() {
        return compileSuccessCount > 0 && iterationDurationsMs.size() >= 1
                && !errorTypesPerIteration.isEmpty()
                && !errorTypesPerIteration.get(0).equals(ExecutionResult.Status.COMPILE_FAILURE.name());
    }

    /** pass-all-tests@k – returns the iteration number where all tests first passed, or -1. */
    public int getPassAllTestsAtK() { return passAllTestsIteration; }

    /** Average time (ms) spent per iteration. */
    public double getMeanIterationDurationMs() {
        return iterationDurationsMs.stream()
                .mapToLong(Long::longValue)
                .average()
                .orElse(0.0);
    }

    /** Total wall-clock duration of the entire pipeline run. */
    public Duration getTotalDuration() {
        Instant end = endTime != null ? endTime : Instant.now();
        return Duration.between(startTime, end);
    }

    public String getSummary() {
        StringBuilder sb = new StringBuilder();
        sb.append("=== Debugging Metrics Summary ===\n");
        sb.append(String.format("  Total iterations      : %d%n", totalIterations));
        sb.append(String.format("  compile-success@1     : %s%n", isCompileSuccessAt1()));
        sb.append(String.format("  pass-all-tests@k      : %s%n",
                passAllTestsIteration > 0 ? "iteration " + passAllTestsIteration : "never"));
        sb.append(String.format("  Mean iteration time   : %.0f ms%n", getMeanIterationDurationMs()));
        sb.append(String.format("  Total wall-clock time : %s%n", getTotalDuration()));
        sb.append(String.format("  Stop reasons          : %s%n", stopReasons));
        sb.append(String.format("  Error types seen      : %s%n", errorTypesPerIteration));
        return sb.toString();
    }

    // ---- Getters ----

    public int getTotalIterations() { return totalIterations; }
    public int getCompileSuccessCount() { return compileSuccessCount; }
    public int getPassAllTestsIteration() { return passAllTestsIteration; }
    public List<String> getStopReasons() { return stopReasons; }
    public List<Long> getIterationDurationsMs() { return iterationDurationsMs; }
    public List<String> getErrorTypesPerIteration() { return errorTypesPerIteration; }
}
