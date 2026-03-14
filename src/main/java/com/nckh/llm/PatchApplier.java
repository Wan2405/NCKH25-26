package com.nckh.llm;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Applies a unified diff patch (produced by the LLM) to Java source files
 * inside the workspace directory.
 *
 * <p>Strategy:
 * <ol>
 *   <li>Try the host {@code patch} command ({@code patch -p1}) for full correctness.</li>
 *   <li>Fall back to a pure-Java heuristic applier when {@code patch} is not available.</li>
 * </ol>
 *
 * <p>The patch text may include markdown fences ({@code ```diff … ```}) or stray
 * prose; these are stripped before application.
 */
public class PatchApplier {

    private static final Logger log = LoggerFactory.getLogger(PatchApplier.class);

    /**
     * Applies the given patch to the workspace rooted at {@code workspaceRoot}.
     *
     * @param workspaceRoot the directory that contains the Maven project
     * @param patchText     unified diff text from the LLM
     * @return {@code true} if the patch was applied successfully
     */
    public boolean apply(Path workspaceRoot, String patchText) {
        if (patchText == null || patchText.isBlank()) {
            log.warn("PatchApplier: received empty patch – nothing to apply");
            return false;
        }

        String cleanPatch = stripMarkdownFences(patchText);

        if (!cleanPatch.contains("---") || !cleanPatch.contains("+++")) {
            log.warn("PatchApplier: patch does not look like a unified diff:\n{}", cleanPatch);
            return false;
        }

        // Prefer the system 'patch' tool
        if (trySystemPatch(workspaceRoot, cleanPatch)) {
            return true;
        }

        // Pure-Java fallback
        return applyJavaFallback(workspaceRoot, cleanPatch);
    }

    // ---- private helpers ----

    private boolean trySystemPatch(Path root, String patch) {
        try {
            Path patchFile = Files.createTempFile("llm_patch_", ".diff");
            Files.writeString(patchFile, patch);

            ProcessBuilder pb = new ProcessBuilder("patch", "-p1", "-i", patchFile.toString());
            pb.directory(root.toFile());
            pb.redirectErrorStream(true);
            Process proc = pb.start();
            String output = new String(proc.getInputStream().readAllBytes());
            int exit = proc.waitFor();

            Files.deleteIfExists(patchFile);

            if (exit == 0) {
                log.info("Patch applied successfully via system 'patch' tool");
                return true;
            }
            log.warn("System 'patch' exited with code {} – output:\n{}", exit, output);
        } catch (IOException | InterruptedException e) {
            log.debug("System 'patch' command not available ({}), using Java fallback", e.getMessage());
        }
        return false;
    }

    /**
     * Minimal pure-Java unified diff applier.
     *
     * <p>Supports the common case of single-file patches with {@code --- a/path}
     * and {@code +++ b/path} headers followed by {@code @@ … @@} hunks.
     */
    private boolean applyJavaFallback(Path root, String patch) {
        try {
            List<FilePatch> filePatches = parsePatch(patch);
            if (filePatches.isEmpty()) {
                log.warn("PatchApplier (Java fallback): no parseable file patches found");
                return false;
            }
            for (FilePatch fp : filePatches) {
                Path target = resolveTargetFile(root, fp.targetPath);
                if (target == null || !Files.exists(target)) {
                    log.warn("PatchApplier: target file not found: {}", fp.targetPath);
                    continue;
                }
                List<String> lines = new ArrayList<>(Files.readAllLines(target));
                applyHunks(lines, fp.hunks);
                Files.writeString(target, String.join("\n", lines) + "\n");
                log.info("PatchApplier (Java fallback): patched {}", target);
            }
            return true;
        } catch (Exception e) {
            log.error("PatchApplier (Java fallback) failed", e);
            return false;
        }
    }

    private static final Pattern FILE_HEADER = Pattern.compile("^\\+\\+\\+\\s+(?:b/)?(.+?)(?:\\t.*)?$");
    private static final Pattern HUNK_HEADER  =
            Pattern.compile("^@@ -(?:(\\d+)(?:,(\\d+))?) \\+(\\d+)(?:,(\\d+))? @@.*$");

    private List<FilePatch> parsePatch(String patch) {
        List<FilePatch> result = new ArrayList<>();
        FilePatch current = null;
        List<String> hunkLines = null;
        int hunkStart = 0;

        for (String rawLine : patch.split("\n")) {
            Matcher fm = FILE_HEADER.matcher(rawLine);
            if (fm.matches()) {
                if (current != null && hunkLines != null) {
                    current.hunks.add(new Hunk(hunkStart, hunkLines));
                }
                current = new FilePatch(fm.group(1).trim());
                result.add(current);
                hunkLines = null;
                continue;
            }
            if (current == null) continue;

            Matcher hm = HUNK_HEADER.matcher(rawLine);
            if (hm.matches()) {
                if (hunkLines != null) {
                    current.hunks.add(new Hunk(hunkStart, hunkLines));
                }
                hunkStart = Integer.parseInt(hm.group(1));
                hunkLines = new ArrayList<>();
                continue;
            }
            if (hunkLines != null) {
                hunkLines.add(rawLine);
            }
        }
        if (current != null && hunkLines != null && !hunkLines.isEmpty()) {
            current.hunks.add(new Hunk(hunkStart, hunkLines));
        }
        return result;
    }

    private void applyHunks(List<String> lines, List<Hunk> hunks) {
        int offset = 0;
        for (Hunk hunk : hunks) {
            int pos = hunk.startLine - 1 + offset; // convert 1-based to 0-based
            List<String> newLines = new ArrayList<>();
            int contextIdx = pos;
            for (String hl : hunk.lines) {
                if (hl.startsWith("-")) {
                    // remove the line at contextIdx
                    if (contextIdx < lines.size()) {
                        lines.remove(contextIdx);
                        offset--;
                    }
                } else if (hl.startsWith("+")) {
                    lines.add(contextIdx, hl.substring(1));
                    contextIdx++;
                    offset++;
                } else {
                    // context line – advance
                    contextIdx++;
                }
            }
        }
    }

    private Path resolveTargetFile(Path root, String targetPath) {
        // Strip leading "a/" or "b/" from git-style paths
        String clean = targetPath.replaceAll("^[ab]/", "");
        Path candidate = root.resolve(clean).normalize();
        if (candidate.startsWith(root)) return candidate;
        return null;
    }

    private String stripMarkdownFences(String text) {
        // Remove ```diff … ``` or ``` … ``` wrappers
        return text.replaceAll("(?s)```[a-z]*\\s*", "").replaceAll("```", "").trim();
    }

    // ---- inner data classes ----

    private static class FilePatch {
        final String targetPath;
        final List<Hunk> hunks = new ArrayList<>();
        FilePatch(String targetPath) { this.targetPath = targetPath; }
    }

    private static class Hunk {
        final int startLine;
        final List<String> lines;
        Hunk(int startLine, List<String> lines) { this.startLine = startLine; this.lines = lines; }
    }
}
