package com.nckh.llm;

import dev.langchain4j.model.chat.ChatLanguageModel;
import dev.langchain4j.model.openai.OpenAiChatModel;
import dev.langchain4j.data.message.SystemMessage;
import dev.langchain4j.data.message.UserMessage;
import dev.langchain4j.data.message.AiMessage;
import dev.langchain4j.model.output.Response;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;

/**
 * Thin wrapper around LangChain4j's {@link ChatLanguageModel} interface.
 *
 * <p>By default this wires to OpenAI's GPT-4o, but any LangChain4j-compatible
 * model (Ollama, Anthropic, Mistral, …) can be injected via the constructor.
 *
 * <p>Configuration is read from environment variables:
 * <ul>
 *   <li>{@code OPENAI_API_KEY} – required for the default OpenAI backend</li>
 *   <li>{@code LLM_MODEL_NAME} – optional model name override (default: {@code gpt-4o})</li>
 *   <li>{@code LLM_TIMEOUT_SECONDS} – optional request timeout (default: {@code 120})</li>
 * </ul>
 */
public class LLMClient {

    private static final Logger log = LoggerFactory.getLogger(LLMClient.class);

    private final ChatLanguageModel model;
    private final PromptBuilder promptBuilder;

    /**
     * Creates an {@code LLMClient} using environment-variable configuration.
     * Falls back to a no-op stub if {@code OPENAI_API_KEY} is not set (useful for offline testing).
     */
    public LLMClient() {
        this(buildDefaultModel(), new PromptBuilder());
    }

    /** Dependency-injection constructor for testing or alternate LLM backends. */
    public LLMClient(ChatLanguageModel model, PromptBuilder promptBuilder) {
        this.model = model;
        this.promptBuilder = promptBuilder;
    }

    /**
     * Sends the error context and current source code to the LLM and returns the
     * raw text of the response (expected to be a unified diff patch).
     *
     * @param errorJson  structured JSON error report from {@link com.nckh.execution.ErrorClassifier}
     * @param sourceCode current content of the Java source file to fix
     * @param buildOutput last build stdout/stderr (truncated by {@link PromptBuilder})
     * @return raw LLM response text (a unified diff patch)
     */
    public String requestPatch(String errorJson, String sourceCode, String buildOutput) {
        String systemMsg = promptBuilder.buildSystemMessage();
        String userMsg   = promptBuilder.buildUserMessage(errorJson, sourceCode, buildOutput);

        log.debug("Sending patch request to LLM ({} chars user message)", userMsg.length());

        try {
            Response<AiMessage> response = model.generate(
                    SystemMessage.from(systemMsg),
                    UserMessage.from(userMsg));

            String patch = response.content().text();
            log.debug("Received patch from LLM ({} chars)", patch == null ? 0 : patch.length());
            return patch;
        } catch (Exception e) {
            log.error("LLM request failed: {}", e.getMessage(), e);
            throw new RuntimeException("LLM request failed: " + e.getMessage(), e);
        }
    }

    // ---- private ----

    private static ChatLanguageModel buildDefaultModel() {
        String apiKey = System.getenv("OPENAI_API_KEY");
        if (apiKey == null || apiKey.isBlank()) {
            log.warn("OPENAI_API_KEY not set – using stub LLM that returns empty patches. "
                     + "Set the environment variable to enable real LLM calls.");
            return buildStubModel();
        }
        String modelName = System.getenv().getOrDefault("LLM_MODEL_NAME", "gpt-4o");
        int timeoutSec   = Integer.parseInt(System.getenv().getOrDefault("LLM_TIMEOUT_SECONDS", "120"));
        log.info("Initialising OpenAI LLM: model={}, timeout={}s", modelName, timeoutSec);
        return OpenAiChatModel.builder()
                .apiKey(apiKey)
                .modelName(modelName)
                .timeout(Duration.ofSeconds(timeoutSec))
                .build();
    }

    /** Stub model used when no API key is configured (e.g., unit tests or CI). */
    private static ChatLanguageModel buildStubModel() {
        return messages -> {
            AiMessage msg = AiMessage.from(
                    "--- a/stub\n+++ b/stub\n@@ -0,0 +0,0 @@\n # stub: OPENAI_API_KEY not configured");
            return Response.from(msg);
        };
    }
}
