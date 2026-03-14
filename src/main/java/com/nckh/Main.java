package com.nckh;

import com.nckh.core.DockerManager;
import com.nckh.core.LoopOrchestrator;
import com.nckh.core.WorkspaceManager;
import com.nckh.execution.BuildEngine;
import com.nckh.execution.ErrorClassifier;
import com.nckh.llm.LLMClient;
import com.nckh.llm.PatchApplier;
import com.nckh.model.DebuggingMetrics;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * CLI entry point for the AI-in-the-loop automated Java debugging pipeline.
 *
 * <h2>Usage</h2>
 * <pre>
 * java -jar ai-debug-pipeline.jar &lt;workspace-dir&gt; [max-iterations] [timeout-seconds]
 *
 * Arguments:
 *   workspace-dir     Path to an existing Maven project directory (must contain pom.xml).
 *   max-iterations    Optional. Maximum feedback loop iterations (default: 10).
 *   timeout-seconds   Optional. Per-iteration Docker container timeout (default: 300).
 *
 * Environment variables:
 *   OPENAI_API_KEY    Required for real LLM calls (uses stub if not set).
 *   LLM_MODEL_NAME    Optional LLM model override (default: gpt-4o).
 *   LLM_TIMEOUT_SECONDS  Optional LLM request timeout (default: 120).
 * </pre>
 *
 * <h2>Example</h2>
 * <pre>
 * export OPENAI_API_KEY=sk-...
 * java -jar ai-debug-pipeline.jar ./workspace 10 300
 * </pre>
 */
public class Main {

    private static final Logger log = LoggerFactory.getLogger(Main.class);

    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("Usage: ai-debug-pipeline <workspace-dir> [max-iterations] [timeout-seconds]");
            System.err.println("  workspace-dir    : path to a Maven project (must contain pom.xml)");
            System.err.println("  max-iterations   : feedback loop limit (default: 10)");
            System.err.println("  timeout-seconds  : per-container timeout   (default: 300)");
            System.exit(1);
        }

        Path workspaceDir   = Paths.get(args[0]).toAbsolutePath();
        int maxIterations   = args.length > 1 ? Integer.parseInt(args[1]) : LoopOrchestrator.DEFAULT_MAX_ITERATIONS;
        int timeoutSeconds  = args.length > 2 ? Integer.parseInt(args[2]) : LoopOrchestrator.DEFAULT_TIMEOUT_SECONDS;

        if (!Files.isDirectory(workspaceDir)) {
            System.err.println("ERROR: workspace-dir does not exist or is not a directory: " + workspaceDir);
            System.exit(1);
        }
        if (!Files.exists(workspaceDir.resolve("pom.xml"))) {
            System.err.println("ERROR: workspace-dir does not contain a pom.xml: " + workspaceDir);
            System.exit(1);
        }

        log.info("AI-in-the-loop Debug Pipeline");
        log.info("  Workspace     : {}", workspaceDir);
        log.info("  Max iterations: {}", maxIterations);
        log.info("  Timeout       : {}s", timeoutSeconds);

        // Copy the workspace so the original is not modified
        WorkspaceManager workspaceManager = new WorkspaceManager();
        Path isolatedWorkspace = null;

        try (DockerManager dockerManager = new DockerManager()) {

            // Prepare isolated copy of the workspace
            isolatedWorkspace = workspaceManager.prepareWorkspaceFromDirectory(workspaceDir);
            log.info("Isolated workspace prepared at: {}", isolatedWorkspace);

            // Wire up the pipeline components
            BuildEngine     buildEngine     = new BuildEngine(dockerManager);
            ErrorClassifier errorClassifier = new ErrorClassifier();
            LLMClient       llmClient       = new LLMClient();
            PatchApplier    patchApplier    = new PatchApplier();

            LoopOrchestrator orchestrator = new LoopOrchestrator(
                    buildEngine, errorClassifier, llmClient, patchApplier, workspaceManager,
                    maxIterations, timeoutSeconds);

            // Run the pipeline
            DebuggingMetrics metrics = orchestrator.run(isolatedWorkspace);

            // Print final metrics
            System.out.println(metrics.getSummary());

            // Exit with code 0 if all tests passed, 1 otherwise
            System.exit(metrics.getPassAllTestsAtK() > 0 ? 0 : 1);

        } catch (Exception e) {
            log.error("Pipeline terminated with unexpected error", e);
            System.exit(2);
        } finally {
            if (isolatedWorkspace != null) {
                new WorkspaceManager().cleanupWorkspace(isolatedWorkspace);
            }
        }
    }
}
