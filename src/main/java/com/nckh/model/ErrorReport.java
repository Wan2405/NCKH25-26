package com.nckh.model;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Structured representation of a single error detected during build or test execution.
 * Produced by {@link com.nckh.execution.ErrorClassifier} and consumed by
 * {@link com.nckh.llm.PromptBuilder} when constructing the LLM feedback request.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ErrorReport {

    public enum ErrorType {
        COMPILE_ERROR,
        RUNTIME_EXCEPTION,
        TEST_FAILURE,
        MISSING_DEPENDENCY,
        BUILD_FAILURE,
        UNKNOWN
    }

    @JsonProperty("type")
    private ErrorType type;

    @JsonProperty("file")
    private String file;

    @JsonProperty("line")
    private Integer line;

    @JsonProperty("category")
    private String category;

    @JsonProperty("message")
    private String message;

    @JsonProperty("raw_output")
    private String rawOutput;

    public ErrorReport() {}

    public ErrorReport(ErrorType type, String file, Integer line, String category, String message) {
        this.type = type;
        this.file = file;
        this.line = line;
        this.category = category;
        this.message = message;
    }

    // ---- Getters & Setters ----

    public ErrorType getType() { return type; }
    public void setType(ErrorType type) { this.type = type; }

    public String getFile() { return file; }
    public void setFile(String file) { this.file = file; }

    public Integer getLine() { return line; }
    public void setLine(Integer line) { this.line = line; }

    public String getCategory() { return category; }
    public void setCategory(String category) { this.category = category; }

    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }

    public String getRawOutput() { return rawOutput; }
    public void setRawOutput(String rawOutput) { this.rawOutput = rawOutput; }

    @Override
    public String toString() {
        return String.format("ErrorReport{type=%s, file='%s', line=%s, category='%s', message='%s'}",
                type, file, line, category, message);
    }
}
