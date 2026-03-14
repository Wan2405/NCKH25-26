package com.nckh.core;

import com.github.dockerjava.api.DockerClient;
import com.github.dockerjava.api.async.ResultCallback;
import com.github.dockerjava.api.command.CreateContainerResponse;
import com.github.dockerjava.api.command.ExecCreateCmdResponse;
import com.github.dockerjava.api.command.PullImageResultCallback;
import com.github.dockerjava.api.model.*;
import com.github.dockerjava.core.DefaultDockerClientConfig;
import com.github.dockerjava.core.DockerClientImpl;
import com.github.dockerjava.httpclient5.ApacheDockerHttpClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.ByteArrayOutputStream;
import java.io.Closeable;
import java.io.IOException;
import java.net.URI;
import java.nio.file.Path;
import java.time.Duration;
import java.util.concurrent.TimeUnit;

/**
 * Manages the full lifecycle of Docker containers used for isolated Java builds.
 *
 * <p>Responsibilities:
 * <ul>
 *   <li>Pull images on demand.</li>
 *   <li>Create containers with CPU/RAM limits and a workspace bind-mount.</li>
 *   <li>Start containers, exec commands, and capture output.</li>
 *   <li>Stop and remove containers when done.</li>
 * </ul>
 *
 * <p>Default resource limits (overridable via constructor):
 * <ul>
 *   <li>CPU:    {@value #DEFAULT_CPU_PERIOD} µs period / {@value #DEFAULT_CPU_QUOTA} µs quota (≈ 2 cores)</li>
 *   <li>Memory: {@value #DEFAULT_MEMORY_BYTES} bytes (512 MiB)</li>
 * </ul>
 */
public class DockerManager implements Closeable {

    private static final Logger log = LoggerFactory.getLogger(DockerManager.class);

    public static final long DEFAULT_MEMORY_BYTES = 512L * 1024 * 1024; // 512 MiB
    public static final long DEFAULT_CPU_PERIOD   = 100_000L;            // µs
    public static final long DEFAULT_CPU_QUOTA    = 200_000L;            // µs  → 2 cores

    private final DockerClient client;
    private final long memoryBytes;
    private final long cpuPeriod;
    private final long cpuQuota;

    // ---- Constructors ----

    /** Creates a DockerManager connected to the default Docker socket with default limits. */
    public DockerManager() {
        this(DEFAULT_MEMORY_BYTES, DEFAULT_CPU_PERIOD, DEFAULT_CPU_QUOTA);
    }

    public DockerManager(long memoryBytes, long cpuPeriod, long cpuQuota) {
        this.memoryBytes = memoryBytes;
        this.cpuPeriod   = cpuPeriod;
        this.cpuQuota    = cpuQuota;
        this.client      = buildDockerClient();
    }

    /** Dependency-injection constructor (for tests). */
    DockerManager(DockerClient client, long memoryBytes, long cpuPeriod, long cpuQuota) {
        this.client      = client;
        this.memoryBytes = memoryBytes;
        this.cpuPeriod   = cpuPeriod;
        this.cpuQuota    = cpuQuota;
    }

    // ---- Public API ----

    /**
     * Ensures the specified image is available locally, pulling it if necessary.
     *
     * @param imageName Docker image name (e.g., {@code "maven:3.9-eclipse-temurin-17"})
     */
    public void ensureImage(String imageName) {
        try {
            client.inspectImageCmd(imageName).exec();
            log.debug("Image already present: {}", imageName);
        } catch (Exception e) {
            log.info("Pulling Docker image: {}", imageName);
            try {
                client.pullImageCmd(imageName)
                        .exec(new PullImageResultCallback())
                        .awaitCompletion(10, TimeUnit.MINUTES);
            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
                throw new RuntimeException("Interrupted while pulling image " + imageName, ie);
            }
        }
    }

    /**
     * Creates and starts a container that bind-mounts the workspace directory
     * at {@code /workspace} inside the container.
     *
     * @param workspacePath absolute host path for the Maven project
     * @param imageName     Docker image to use
     * @return the container ID
     */
    public String startBuildContainer(Path workspacePath, String imageName) {
        ensureImage(imageName);

        Volume containerWorkspace = new Volume("/workspace");
        Bind bind = new Bind(workspacePath.toAbsolutePath().toString(), containerWorkspace);

        HostConfig hostConfig = HostConfig.newHostConfig()
                .withBinds(bind)
                .withMemory(memoryBytes)
                .withMemorySwap(memoryBytes)          // disable swap
                .withCpuPeriod(cpuPeriod)
                .withCpuQuota(cpuQuota)
                .withNetworkMode("bridge");            // allow Maven to download deps

        CreateContainerResponse container = client.createContainerCmd(imageName)
                .withWorkingDir("/workspace")
                .withHostConfig(hostConfig)
                // Keep the container alive so we can exec into it
                .withCmd("tail", "-f", "/dev/null")
                .exec();

        String id = container.getId();
        client.startContainerCmd(id).exec();
        log.info("Container started: {} (image={})", id, imageName);
        return id;
    }

    /**
     * Executes a command inside a running container and captures stdout/stderr.
     *
     * @param containerId     the container ID returned by {@link #startBuildContainer}
     * @param command         command and arguments
     * @param timeoutSeconds  maximum seconds to wait for the command to finish
     * @return an {@link ExecResult} with the captured output and timeout flag
     */
    public ExecResult execInContainer(String containerId, String[] command, int timeoutSeconds) {
        ExecCreateCmdResponse exec = client.execCreateCmd(containerId)
                .withCmd(command)
                .withAttachStdout(true)
                .withAttachStderr(true)
                .withWorkingDir("/workspace")
                .exec();

        ByteArrayOutputStream stdout = new ByteArrayOutputStream();
        ByteArrayOutputStream stderr = new ByteArrayOutputStream();

        FrameCollector callback = new FrameCollector(stdout, stderr);

        try {
            client.execStartCmd(exec.getId())
                    .exec(callback)
                    .awaitCompletion(timeoutSeconds, TimeUnit.SECONDS);

            boolean timedOut = !callback.isCompleted();
            return new ExecResult(stdout.toString(), stderr.toString(), timedOut);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return new ExecResult(stdout.toString(), stderr.toString(), true);
        }
    }

    /**
     * Stops and removes the specified container.
     *
     * @param containerId container ID to clean up
     */
    public void stopAndRemoveContainer(String containerId) {
        try {
            client.stopContainerCmd(containerId).withTimeout(10).exec();
        } catch (Exception e) {
            log.warn("Could not stop container {} (may already be stopped): {}", containerId, e.getMessage());
        }
        try {
            client.removeContainerCmd(containerId).withForce(true).exec();
            log.info("Container removed: {}", containerId);
        } catch (Exception e) {
            log.warn("Could not remove container {}: {}", containerId, e.getMessage());
        }
    }

    @Override
    public void close() {
        try {
            client.close();
        } catch (IOException e) {
            log.warn("Error closing Docker client", e);
        }
    }

    // ---- Private helpers ----

    private static DockerClient buildDockerClient() {
        DefaultDockerClientConfig config = DefaultDockerClientConfig.createDefaultConfigBuilder().build();
        ApacheDockerHttpClient httpClient = new ApacheDockerHttpClient.Builder()
                .dockerHost(config.getDockerHost())
                .sslConfig(config.getSSLConfig())
                .maxConnections(10)
                .connectionTimeout(Duration.ofSeconds(30))
                .responseTimeout(Duration.ofMinutes(10))
                .build();
        return DockerClientImpl.getInstance(config, httpClient);
    }

    // ---- Inner types ----

    /**
     * Captures stdout and stderr frames from an exec stream.
     */
    private static class FrameCollector extends ResultCallback.Adapter<Frame> {
        private final ByteArrayOutputStream stdout;
        private final ByteArrayOutputStream stderr;
        private volatile boolean completed = false;

        FrameCollector(ByteArrayOutputStream stdout, ByteArrayOutputStream stderr) {
            this.stdout = stdout;
            this.stderr = stderr;
        }

        @Override
        public void onNext(Frame frame) {
            if (frame == null) return;
            try {
                switch (frame.getStreamType()) {
                    case STDOUT -> stdout.write(frame.getPayload());
                    case STDERR -> stderr.write(frame.getPayload());
                    default     -> { /* ignore RAW / STDIN */ }
                }
            } catch (IOException e) {
                log.warn("Error writing frame payload", e);
            }
        }

        @Override
        public void onComplete() {
            completed = true;
        }

        boolean isCompleted() { return completed; }
    }

    /**
     * Immutable result of a container exec call.
     *
     * @param stdout   captured standard output
     * @param stderr   captured standard error
     * @param timedOut {@code true} if the command did not finish within the timeout
     */
    public record ExecResult(String stdout, String stderr, boolean timedOut) {}
}
