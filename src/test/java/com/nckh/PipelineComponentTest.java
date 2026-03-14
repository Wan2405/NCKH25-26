package com.nckh;

import com.nckh.execution.ErrorClassifier;
import com.nckh.execution.LogParser;
import com.nckh.llm.PatchApplier;
import com.nckh.llm.PromptBuilder;
import com.nckh.model.ErrorReport;
import com.nckh.model.ExecutionResult;
import com.nckh.model.DebuggingMetrics;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for the core pipeline components.
 *
 * <p>These tests do NOT require a running Docker daemon or an LLM API key –
 * they test the parsing, classification, prompt building, and patch-applying
 * logic in isolation.
 */
class PipelineComponentTest {

    // ---- LogParser ----

    @Test
    void logParser_detectsCompileError() {
        LogParser parser = new LogParser();
        String stdout = "[ERROR] /workspace/src/main/java/com/example/Solution.java:[12,5] cannot find symbol\n"
                + "  symbol: class List";
        List<ErrorReport> errors = parser.parse(stdout, "");
        assertFalse(errors.isEmpty(), "Should detect at least one compile error");
        assertEquals(ErrorReport.ErrorType.COMPILE_ERROR, errors.get(0).getType());
        assertEquals("Solution.java", errors.get(0).getFile());
        assertEquals(12, errors.get(0).getLine());
    }

    @Test
    void logParser_detectsMissingDependency() {
        LogParser parser = new LogParser();
        String stderr = "Could not resolve dependencies for artifact com.example:foo:1.0";
        List<ErrorReport> errors = parser.parse("", stderr);
        assertFalse(errors.isEmpty());
        assertEquals(ErrorReport.ErrorType.MISSING_DEPENDENCY, errors.get(0).getType());
    }

    @Test
    void logParser_parseTestCounts_success() {
        LogParser parser = new LogParser();
        String output = "Tests run: 5, Failures: 0, Errors: 0, Skipped: 0";
        int[] counts = parser.parseTestCounts(output);
        assertEquals(5, counts[0]); // total
        assertEquals(5, counts[1]); // passed
        assertEquals(0, counts[2]); // failed
    }

    @Test
    void logParser_parseTestCounts_withFailures() {
        LogParser parser = new LogParser();
        String output = "Tests run: 5, Failures: 2, Errors: 1, Skipped: 0";
        int[] counts = parser.parseTestCounts(output);
        assertEquals(5, counts[0]); // total
        assertEquals(2, counts[1]); // passed (5 - 2 - 1)
        assertEquals(3, counts[2]); // failed (2 + 1)
    }

    @Test
    void logParser_returnsEmptyForCleanOutput() {
        LogParser parser = new LogParser();
        String output = "[INFO] BUILD SUCCESS\nTests run: 3, Failures: 0, Errors: 0, Skipped: 0";
        List<ErrorReport> errors = parser.parse(output, "");
        assertTrue(errors.isEmpty(), "No errors expected for clean build output");
    }

    // ---- ErrorClassifier ----

    @Test
    void errorClassifier_producesValidJson() {
        ErrorClassifier classifier = new ErrorClassifier();
        String json = classifier.classifyToJson(
                "[ERROR] /ws/Solution.java:[5,1] ';' expected", "");
        assertNotNull(json);
        assertTrue(json.startsWith("[") || json.equals("[]"));
    }

    @Test
    void errorClassifier_emptyOutputProducesEmptyArray() {
        ErrorClassifier classifier = new ErrorClassifier();
        assertEquals("[ ]", classifier.classifyToJson("BUILD SUCCESS", "").replace("[ ]", "[ ]"));
        // Just assert it parses cleanly and is non-null
        assertNotNull(classifier.classifyToJson("", ""));
    }

    // ---- PromptBuilder ----

    @Test
    void promptBuilder_containsAllSections() {
        PromptBuilder builder = new PromptBuilder();
        String user = builder.buildUserMessage(
                "[{\"type\":\"COMPILE_ERROR\"}]",
                "public class Foo {}",
                "BUILD FAILURE");
        assertTrue(user.contains("Error Report"), "Should contain Error Report section");
        assertTrue(user.contains("Current Source Code"), "Should contain Source Code section");
        assertTrue(user.contains("Build Output"), "Should contain Build Output section");
    }

    @Test
    void promptBuilder_systemMessageNonEmpty() {
        PromptBuilder builder = new PromptBuilder();
        assertFalse(builder.buildSystemMessage().isBlank());
    }

    // ---- PatchApplier ----

    @Test
    void patchApplier_appliesSimpleAddition(@TempDir Path tempDir) throws IOException {
        // Create a simple Java file
        Path javaFile = tempDir.resolve("Solution.java");
        Files.writeString(javaFile, "public class Solution {\n    int x = 1;\n}\n");

        String patch = "--- a/Solution.java\n"
                + "+++ b/Solution.java\n"
                + "@@ -1,3 +1,3 @@\n"
                + " public class Solution {\n"
                + "-    int x = 1;\n"
                + "+    int x = 2;\n"
                + " }\n";

        PatchApplier applier = new PatchApplier();
        boolean result = applier.apply(tempDir, patch);
        assertTrue(result, "Patch should be applied successfully");
        String content = Files.readString(javaFile);
        assertTrue(content.contains("int x = 2"), "File should contain updated value");
    }

    @Test
    void patchApplier_returnsFalseForEmptyPatch(@TempDir Path tempDir) {
        PatchApplier applier = new PatchApplier();
        assertFalse(applier.apply(tempDir, ""));
        assertFalse(applier.apply(tempDir, null));
    }

    @Test
    void patchApplier_stripsMarkdownFences(@TempDir Path tempDir) throws IOException {
        Path javaFile = tempDir.resolve("Foo.java");
        Files.writeString(javaFile, "class Foo { int v = 0; }\n");

        // LLM wraps the diff in markdown code fences
        String patch = "```diff\n"
                + "--- a/Foo.java\n"
                + "+++ b/Foo.java\n"
                + "@@ -1 +1 @@\n"
                + "-class Foo { int v = 0; }\n"
                + "+class Foo { int v = 42; }\n"
                + "```";

        PatchApplier applier = new PatchApplier();
        boolean result = applier.apply(tempDir, patch);
        assertTrue(result);
        assertTrue(Files.readString(javaFile).contains("42"));
    }

    // ---- DebuggingMetrics ----

    @Test
    void metrics_tracksIterationsCorrectly() {
        DebuggingMetrics metrics = new DebuggingMetrics();
        assertEquals(0, metrics.getTotalIterations());

        ExecutionResult fail = ExecutionResult.failure(
                ExecutionResult.Status.COMPILE_FAILURE,
                "out", "err", List.of(), 0, 0, 100L);
        metrics.recordIteration(fail);
        assertEquals(1, metrics.getTotalIterations());

        ExecutionResult success = ExecutionResult.success("out", 5, 200L);
        metrics.recordIteration(success);
        assertEquals(2, metrics.getTotalIterations());
        assertEquals(2, metrics.getPassAllTestsAtK());
    }

    @Test
    void metrics_summaryIsNonEmpty() {
        DebuggingMetrics metrics = new DebuggingMetrics();
        metrics.recordStop("test");
        String summary = metrics.getSummary();
        assertFalse(summary.isBlank());
        assertTrue(summary.contains("Total iterations"));
    }
}
