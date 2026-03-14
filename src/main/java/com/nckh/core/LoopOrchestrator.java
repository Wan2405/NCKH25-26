package com.nckh.core;

import com.nckh.execution.BuildEngine;
import com.nckh.execution.ErrorClassifier;
import com.nckh.llm.LLMClient;
import com.nckh.llm.PatchApplier;
import com.nckh.model.DebuggingMetrics;
import com.nckh.model.ErrorReport;
import com.nckh.model.ExecutionResult;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.file.Path;
import java.util.List;

/**
 * Central state-machine orchestrator for the AI-in-the-loop automated debugging pipeline.
 *
 * <h2>Pipeline States</h2>
 * <pre>
 * IDLE ──► PROVISION ──► BUILD_AND_TEST ──► (success?) ──► DONE
 *                              │                                ▲
 *                              ▼ (failure)                      │
 *                        PARSE_ERRORS                           │
 *                              │                                │
 *                              ▼                                │
 *                        LLM_FEEDBACK  ────────────────────────►│
 *                              │                                │
 *                              ▼                                │
 *                        APPLY_PATCH ──► BUILD_AND_TEST (loop)  │
 *                              │                                │
 *                              ▼ (stop condition met)           │
 *                            DONE ───────────────────────────────
 * </pre>
 *
 * <h2>Stop Conditions</h2>
 * <ol>
 *   <li><b>SUCCESS</b> – all JUnit tests pass.</li>
 *   <li><b>MAX_ITERATIONS</b> – loop count reaches {@link #maxIterations}.</li>
 *   <li><b>STAGNATION</b> – no improvement in pass count for ≥ {@value #STAGNATION_THRESHOLD} consecutive iterations.</li>
 *   <li><b>TIMEOUT / RESOURCE</b> – container timed out or hit a resource limit.</li>
 * </ol>
 */
public class LoopOrchestrator {

    private static final Logger log = LoggerFactory.getLogger(LoopOrchestrator.class);

    public static final int DEFAULT_MAX_ITERATIONS  = 10;
    public static final int DEFAULT_TIMEOUT_SECONDS = 300;
    static final int STAGNATION_THRESHOLD = 2;

    // ---- State machine states ----
    private enum State {
        IDLE, PROVISION, BUILD_AND_TEST, PARSE_ERRORS, LLM_FEEDBACK, APPLY_PATCH, DONE
    }

    private final BuildEngine      buildEngine;
    private final ErrorClassifier  errorClassifier;
    private final LLMClient        llmClient;
    private final PatchApplier     patchApplier;
    private final WorkspaceManager workspaceManager;

    private final int maxIterations;
    private final int timeoutSeconds;

    // ---- Constructor ----

    public LoopOrchestrator(BuildEngine buildEngine,
                            ErrorClassifier errorClassifier,
                            LLMClient llmClient,
                            PatchApplier patchApplier,
                            WorkspaceManager workspaceManager) {
        this(buildEngine, errorClassifier, llmClient, patchApplier, workspaceManager,
             DEFAULT_MAX_ITERATIONS, DEFAULT_TIMEOUT_SECONDS);
    }

    public LoopOrchestrator(BuildEngine buildEngine,
                            ErrorClassifier errorClassifier,
                            LLMClient llmClient,
                            PatchApplier patchApplier,
                            WorkspaceManager workspaceManager,
                            int maxIterations,
                            int timeoutSeconds) {
        this.buildEngine      = buildEngine;
        this.errorClassifier  = errorClassifier;
        this.llmClient        = llmClient;
        this.patchApplier     = patchApplier;
        this.workspaceManager = workspaceManager;
        this.maxIterations    = maxIterations;
        this.timeoutSeconds   = timeoutSeconds;
    }

    // ---- Main entry point ----

    /**
     * Runs the full debugging pipeline for the Maven project located at
     * {@code workspacePath}.
     *
     * <p>The workspace must already be prepared by {@link WorkspaceManager} before
     * this method is called.  The workspace directory is NOT deleted by this method;
     * call {@link WorkspaceManager#cleanupWorkspace} when done.
     *
     * @param workspacePath path of the prepared Maven project workspace
     * @return final {@link DebuggingMetrics} collected across all iterations
     */
    public DebuggingMetrics run(Path workspacePath) {
        DebuggingMetrics metrics = new DebuggingMetrics();
        State state = State.PROVISION;

        ExecutionResult lastResult = null;
        int stagnationCount = 0;
        int lastPassedTests = -1;

        log.info("=== LoopOrchestrator starting (maxIterations={}, timeout={}s) ===",
                maxIterations, timeoutSeconds);

        while (state != State.DONE) {
            log.info("--- State: {} | iteration {}/{} ---", state, metrics.getTotalIterations(), maxIterations);

            switch (state) {

                case PROVISION -> {
                    // Workspace is already prepared by WorkspaceManager; just move on
                    log.info("Workspace ready at: {}", workspacePath);
                    state = State.BUILD_AND_TEST;
                }

                case BUILD_AND_TEST -> {
                    lastResult = buildEngine.runTests(workspacePath, timeoutSeconds);
                    metrics.recordIteration(lastResult);
                    log.info("Build result: {}", lastResult);

                    if (lastResult.isSuccess()) {
                        metrics.recordStop("pass-all-tests");
                        state = State.DONE;
                    } else if (lastResult.isTerminal()) {
                        metrics.recordStop(lastResult.getStatus().name());
                        state = State.DONE;
                    } else if (metrics.getTotalIterations() >= maxIterations) {
                        metrics.recordStop("max-iterations-reached");
                        state = State.DONE;
                    } else {
                        // Check stagnation
                        int currentPassed = lastResult.getPassedTests();
                        if (currentPassed <= lastPassedTests) {
                            stagnationCount++;
                        } else {
                            stagnationCount = 0;
                        }
                        lastPassedTests = currentPassed;

                        if (stagnationCount >= STAGNATION_THRESHOLD) {
                            log.warn("Stagnation detected ({} consecutive iterations with no improvement)", stagnationCount);
                            metrics.recordStop("stagnation");
                            state = State.DONE;
                        } else {
                            state = State.PARSE_ERRORS;
                        }
                    }
                }

                case PARSE_ERRORS -> {
                    List<ErrorReport> errors = lastResult.getErrors();
                    if (errors == null || errors.isEmpty()) {
                        log.warn("No parseable errors found despite BUILD FAILURE – stopping");
                        metrics.recordStop("no-parseable-errors");
                        state = State.DONE;
                    } else {
                        log.info("Parsed {} error(s). Primary: {}", errors.size(), errors.get(0));
                        state = State.LLM_FEEDBACK;
                    }
                }

                case LLM_FEEDBACK -> {
                    try {
                        String errorJson = errorClassifier.classifyToJson(
                                lastResult.getStdout(), lastResult.getStderr());
                        String sourceCode = readAllSources(workspacePath);
                        String buildOutput = (lastResult.getStdout() == null ? "" : lastResult.getStdout())
                                           + "\n" + (lastResult.getStderr() == null ? "" : lastResult.getStderr());

                        log.info("Requesting patch from LLM...");
                        String patch = llmClient.requestPatch(errorJson, sourceCode, buildOutput);
                        log.debug("LLM patch:\n{}", patch);

                        // Store patch for APPLY_PATCH state
                        state = State.APPLY_PATCH;
                        // Pass patch through a field — use ThreadLocal-free approach: pass it inline
                        boolean applied = patchApplier.apply(workspacePath, patch);
                        if (!applied) {
                            log.warn("Patch could not be applied – stopping");
                            metrics.recordStop("patch-apply-failed");
                            state = State.DONE;
                        } else {
                            state = State.BUILD_AND_TEST;
                        }
                    } catch (Exception e) {
                        log.error("LLM feedback step failed", e);
                        metrics.recordStop("llm-error: " + e.getMessage());
                        state = State.DONE;
                    }
                }

                case APPLY_PATCH -> {
                    // Handled inline in LLM_FEEDBACK; this state is a no-op if reached directly
                    state = State.BUILD_AND_TEST;
                }

                case DONE -> { /* exit loop */ }
            }
        }

        log.info("=== LoopOrchestrator finished ===");
        log.info(metrics.getSummary());
        return metrics;
    }

    // ---- helpers ----

    /**
     * Reads all {@code .java} files under {@code src/main/java} in the workspace
     * and concatenates them for the LLM context window.
     */
    private String readAllSources(Path workspace) {
        StringBuilder sb = new StringBuilder();
        try {
            Path srcMain = workspace.resolve("src/main/java");
            if (!srcMain.toFile().exists()) return "";
            java.nio.file.Files.walk(srcMain)
                    .filter(p -> p.toString().endsWith(".java"))
                    .forEach(p -> {
                        try {
                            sb.append("// File: ").append(workspace.relativize(p)).append("\n");
                            sb.append(java.nio.file.Files.readString(p)).append("\n\n");
                        } catch (Exception e) {
                            log.warn("Could not read source file {}", p);
                        }
                    });
        } catch (Exception e) {
            log.warn("Could not enumerate source files in workspace", e);
        }
        return sb.toString();
    }
}
