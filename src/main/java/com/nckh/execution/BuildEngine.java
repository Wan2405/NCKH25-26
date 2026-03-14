package com.nckh.execution;

import com.github.dockerjava.api.DockerClient;
import com.github.dockerjava.api.command.CreateContainerResponse;
import com.github.dockerjava.api.command.ExecCreateCmdResponse;
import com.github.dockerjava.api.model.Bind;
import com.github.dockerjava.api.model.HostConfig;
import com.github.dockerjava.api.model.Volume;
import com.nckh.core.DockerManager;
import com.nckh.model.ErrorReport;
import com.nckh.model.ExecutionResult;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.ByteArrayOutputStream;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * Triggers Maven build-and-test commands inside an isolated Docker container.
 *
 * <p>The container mounts the workspace directory provided by
 * {@link com.nckh.core.WorkspaceManager} and runs {@code mvn clean test}.
 * All stdout, stderr, and JUnit XML output are captured and returned as an
 * {@link ExecutionResult}.
 *
 * <p>Container lifecycle (start/stop/remove) is delegated to {@link DockerManager}.
 */
public class BuildEngine {

    private static final Logger log = LoggerFactory.getLogger(BuildEngine.class);

    /** Docker image to use for builds. Must contain JDK 17 + Maven. */
    public static final String BUILD_IMAGE = "maven:3.9-eclipse-temurin-17";

    private final DockerManager dockerManager;
    private final ErrorClassifier errorClassifier;
    private final LogParser logParser;

    public BuildEngine(DockerManager dockerManager) {
        this.dockerManager = dockerManager;
        this.errorClassifier = new ErrorClassifier();
        this.logParser = new LogParser();
    }

    /**
     * Runs {@code mvn clean test} inside a fresh Docker container that mounts
     * the given workspace directory.
     *
     * @param workspacePath absolute path of the Maven project on the host
     * @param timeoutSeconds container execution timeout
     * @return the captured {@link ExecutionResult}
     */
    public ExecutionResult runTests(Path workspacePath, int timeoutSeconds) {
        long start = System.currentTimeMillis();
        String containerId = null;
        try {
            containerId = dockerManager.startBuildContainer(workspacePath, BUILD_IMAGE);
            log.info("Started container {} for workspace {}", containerId, workspacePath);

            // Execute mvn clean test
            String[] cmd = {"mvn", "clean", "test", "--batch-mode", "-Dsurefire.failIfNoSpecifiedTests=false"};
            DockerManager.ExecResult execResult =
                    dockerManager.execInContainer(containerId, cmd, timeoutSeconds);

            long duration = System.currentTimeMillis() - start;

            String combined = execResult.stdout() + "\n" + execResult.stderr();

            if (execResult.timedOut()) {
                log.warn("Container execution timed out after {}s", timeoutSeconds);
                return ExecutionResult.failure(
                        ExecutionResult.Status.TIMEOUT,
                        execResult.stdout(), execResult.stderr(),
                        List.of(), 0, 0, duration);
            }

            int[] counts = logParser.parseTestCounts(combined);
            int total   = counts[0];
            int passed  = counts[1];
            int failed  = counts[2];

            List<ErrorReport> errors = errorClassifier.classify(execResult.stdout(), execResult.stderr());

            // Determine overall status
            boolean buildOk = !combined.contains("BUILD FAILURE");
            boolean hasCompileErrors = errors.stream()
                    .anyMatch(e -> e.getType() == ErrorReport.ErrorType.COMPILE_ERROR
                            || e.getType() == ErrorReport.ErrorType.MISSING_DEPENDENCY);

            if (hasCompileErrors) {
                return ExecutionResult.failure(
                        ExecutionResult.Status.COMPILE_FAILURE,
                        execResult.stdout(), execResult.stderr(), errors, total, passed, duration);
            }
            if (failed > 0 || (!errors.isEmpty() && buildOk)) {
                return ExecutionResult.failure(
                        ExecutionResult.Status.TEST_FAILURE,
                        execResult.stdout(), execResult.stderr(), errors, total, passed, duration);
            }
            if (!buildOk) {
                return ExecutionResult.failure(
                        ExecutionResult.Status.COMPILE_FAILURE,
                        execResult.stdout(), execResult.stderr(), errors, total, passed, duration);
            }

            log.info("Build succeeded. Tests: {}/{} passed", passed, total);
            return ExecutionResult.success(execResult.stdout(), total, duration);

        } catch (Exception e) {
            long duration = System.currentTimeMillis() - start;
            log.error("BuildEngine encountered an internal error", e);
            ErrorReport err = new ErrorReport(
                    ErrorReport.ErrorType.BUILD_FAILURE, null, null,
                    "internal_error", e.getMessage());
            return ExecutionResult.failure(
                    ExecutionResult.Status.INTERNAL_ERROR,
                    "", e.getMessage(), List.of(err), 0, 0, duration);
        } finally {
            if (containerId != null) {
                dockerManager.stopAndRemoveContainer(containerId);
            }
        }
    }
}
