package com.nckh.llm;

import com.nckh.model.ErrorReport;
import com.nckh.model.ExecutionResult;

import java.util.List;

/**
 * Constructs the LangChain4j prompt string that is sent to the LLM when
 * requesting a patch to fix failing Java code.
 *
 * <p>The prompt instructs the LLM to return ONLY a unified diff patch
 * (no prose, no markdown fences) so that {@link PatchApplier} can apply
 * it directly with {@code patch -p1}.
 */
public class PromptBuilder {

    private static final String SYSTEM_PROMPT =
            "You are an expert Java developer and automated debugging assistant. "
            + "You will receive a JSON error report and the current Java source code. "
            + "Your task is to fix the code so that all JUnit tests pass. "
            + "Return ONLY a unified diff patch in the standard 'diff -u' format. "
            + "Do NOT include any explanation, markdown code fences, or prose outside the diff.";

    private static final String USER_TEMPLATE =
            "## Error Report (JSON)\n"
            + "```json\n"
            + "{errorJson}\n"
            + "```\n\n"
            + "## Current Source Code\n"
            + "```java\n"
            + "{sourceCode}\n"
            + "```\n\n"
            + "## Build Output\n"
            + "```\n"
            + "{buildOutput}\n"
            + "```\n\n"
            + "Return the unified diff patch now:";

    /**
     * Builds the system (role) message content for the LLM API call.
     */
    public String buildSystemMessage() {
        return SYSTEM_PROMPT;
    }

    /**
     * Builds the user message that includes the error context and source code.
     *
     * @param errorJson    JSON string produced by {@link com.nckh.execution.ErrorClassifier}
     * @param sourceCode   content of the Java source file(s) to fix
     * @param buildOutput  truncated stdout/stderr from the last build run
     * @return the formatted user message
     */
    public String buildUserMessage(String errorJson, String sourceCode, String buildOutput) {
        return USER_TEMPLATE
                .replace("{errorJson}", errorJson == null ? "[]" : errorJson)
                .replace("{sourceCode}", sourceCode == null ? "" : sourceCode)
                .replace("{buildOutput}", truncate(buildOutput, 3000));
    }

    /**
     * Convenience overload: builds the user message from a full {@link ExecutionResult}.
     */
    public String buildUserMessage(ExecutionResult result, String sourceCode,
                                   String errorJson) {
        String buildOut = "";
        if (result != null) {
            buildOut = (result.getStdout() == null ? "" : result.getStdout())
                     + "\n"
                     + (result.getStderr() == null ? "" : result.getStderr());
        }
        return buildUserMessage(errorJson, sourceCode, buildOut);
    }

    // ---- helpers ----

    private String truncate(String s, int maxLen) {
        if (s == null) return "";
        if (s.length() <= maxLen) return s;
        return s.substring(s.length() - maxLen); // keep the tail (most recent output)
    }
}
