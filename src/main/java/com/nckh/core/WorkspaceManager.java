package com.nckh.core;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.List;
import java.util.Map;

/**
 * Prepares and manages the Maven project workspace that will be bind-mounted into
 * the Docker container for each build cycle.
 *
 * <p>Responsibilities:
 * <ul>
 *   <li>Copy input source files, JUnit test files, and {@code pom.xml} into a
 *       temporary workspace directory.</li>
 *   <li>Replace individual source files in the workspace after a patch is applied.</li>
 *   <li>Clean up the workspace directory when the pipeline finishes.</li>
 * </ul>
 *
 * <p>Workspace layout (mirrors a standard Maven project):
 * <pre>
 * workspace/
 *   pom.xml
 *   src/
 *     main/java/com/example/   ← production code
 *     test/java/com/example/   ← JUnit tests
 * </pre>
 */
public class WorkspaceManager {

    private static final Logger log = LoggerFactory.getLogger(WorkspaceManager.class);

    private final Path baseDir;   // root under which temporary workspaces are created

    /**
     * Creates a WorkspaceManager that stores temporary workspaces under the system
     * temp directory ({@code java.io.tmpdir}).
     */
    public WorkspaceManager() {
        this(Path.of(System.getProperty("java.io.tmpdir")));
    }

    public WorkspaceManager(Path baseDir) {
        this.baseDir = baseDir;
    }

    /**
     * Creates an isolated workspace directory and populates it with the provided
     * Maven project files.
     *
     * @param pomXmlPath      path to the {@code pom.xml} file
     * @param sourceFiles     map of relative path → file content for production Java sources
     *                        (e.g., {@code "src/main/java/com/example/Solution.java"} → code)
     * @param testFiles       map of relative path → file content for JUnit test sources
     * @return the path of the prepared workspace directory (to be mounted in Docker)
     * @throws IOException if file I/O fails
     */
    public Path prepareWorkspace(Path pomXmlPath,
                                 Map<String, String> sourceFiles,
                                 Map<String, String> testFiles) throws IOException {
        Path workspace = Files.createTempDirectory(baseDir, "nckh_workspace_");
        log.info("Created workspace at: {}", workspace);

        // Copy pom.xml
        Files.copy(pomXmlPath, workspace.resolve("pom.xml"), StandardCopyOption.REPLACE_EXISTING);

        // Write source files
        writeFiles(workspace, sourceFiles);

        // Write test files
        writeFiles(workspace, testFiles);

        return workspace;
    }

    /**
     * Convenience overload: creates a workspace from an existing Maven project directory
     * by copying its entire content.
     *
     * @param projectDir existing Maven project directory (must contain {@code pom.xml})
     * @return path of the new isolated workspace copy
     * @throws IOException if copying fails
     */
    public Path prepareWorkspaceFromDirectory(Path projectDir) throws IOException {
        Path workspace = Files.createTempDirectory(baseDir, "nckh_workspace_");
        log.info("Copying project {} → workspace {}", projectDir, workspace);
        copyDirectory(projectDir, workspace);
        return workspace;
    }

    /**
     * Updates a single source file inside an already-prepared workspace.
     *
     * @param workspace    the workspace directory
     * @param relativePath relative path from workspace root (e.g., {@code "src/main/java/…/Solution.java"})
     * @param content      new file content
     * @throws IOException if file I/O fails
     */
    public void updateSourceFile(Path workspace, String relativePath, String content) throws IOException {
        Path target = workspace.resolve(relativePath).normalize();
        if (!target.startsWith(workspace)) {
            throw new IllegalArgumentException("Path traversal rejected: " + relativePath);
        }
        Files.createDirectories(target.getParent());
        Files.writeString(target, content);
        log.debug("Updated file in workspace: {}", relativePath);
    }

    /**
     * Reads the content of a file inside the workspace.
     *
     * @param workspace    the workspace directory
     * @param relativePath relative path from workspace root
     * @return file content as a string
     * @throws IOException if the file cannot be read
     */
    public String readSourceFile(Path workspace, String relativePath) throws IOException {
        Path target = workspace.resolve(relativePath).normalize();
        if (!target.startsWith(workspace)) {
            throw new IllegalArgumentException("Path traversal rejected: " + relativePath);
        }
        return Files.readString(target);
    }

    /**
     * Recursively deletes the workspace directory and all its contents.
     *
     * @param workspace the workspace directory to remove
     */
    public void cleanupWorkspace(Path workspace) {
        if (workspace == null || !Files.exists(workspace)) return;
        try {
            Files.walkFileTree(workspace, new SimpleFileVisitor<>() {
                @Override
                public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                    Files.delete(file);
                    return FileVisitResult.CONTINUE;
                }
                @Override
                public FileVisitResult postVisitDirectory(Path dir, IOException exc) throws IOException {
                    Files.delete(dir);
                    return FileVisitResult.CONTINUE;
                }
            });
            log.info("Workspace cleaned up: {}", workspace);
        } catch (IOException e) {
            log.warn("Failed to fully clean workspace {}: {}", workspace, e.getMessage());
        }
    }

    // ---- private helpers ----

    private void writeFiles(Path workspace, Map<String, String> files) throws IOException {
        if (files == null) return;
        for (Map.Entry<String, String> entry : files.entrySet()) {
            Path target = workspace.resolve(entry.getKey()).normalize();
            if (!target.startsWith(workspace)) {
                throw new IllegalArgumentException("Path traversal rejected: " + entry.getKey());
            }
            Files.createDirectories(target.getParent());
            Files.writeString(target, entry.getValue());
            log.debug("Wrote file to workspace: {}", entry.getKey());
        }
    }

    private void copyDirectory(Path src, Path dst) throws IOException {
        Files.walkFileTree(src, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) throws IOException {
                Files.createDirectories(dst.resolve(src.relativize(dir)));
                return FileVisitResult.CONTINUE;
            }
            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                Files.copy(file, dst.resolve(src.relativize(file)), StandardCopyOption.REPLACE_EXISTING);
                return FileVisitResult.CONTINUE;
            }
        });
    }
}
