package com.nckh.execution;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.nckh.model.ErrorReport;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;

/**
 * Converts raw log output into a structured JSON error report.
 *
 * <p>This class wraps {@link LogParser} and serialises the resulting
 * {@link ErrorReport} list to a JSON string that can be passed directly
 * to the LLM prompt template.
 *
 * <p>Example output:
 * <pre>
 * [
 *   {
 *     "type": "COMPILE_ERROR",
 *     "file": "Solution.java",
 *     "line": 12,
 *     "category": "missing_import",
 *     "message": "cannot find symbol: class List"
 *   }
 * ]
 * </pre>
 */
public class ErrorClassifier {

    private static final Logger log = LoggerFactory.getLogger(ErrorClassifier.class);

    private final LogParser logParser = new LogParser();
    private final ObjectMapper mapper = new ObjectMapper()
            .enable(SerializationFeature.INDENT_OUTPUT);

    /**
     * Classifies errors from raw build output and returns a pretty-printed JSON string.
     *
     * @param stdout standard output captured from the container
     * @param stderr standard error captured from the container
     * @return JSON array of {@link ErrorReport} objects; {@code "[]"} when no errors are found
     */
    public String classifyToJson(String stdout, String stderr) {
        List<ErrorReport> errors = logParser.parse(stdout, stderr);
        try {
            return mapper.writeValueAsString(errors);
        } catch (Exception e) {
            log.error("Failed to serialise error reports to JSON", e);
            return "[]";
        }
    }

    /**
     * Returns the parsed list of {@link ErrorReport} objects without JSON serialisation.
     *
     * @param stdout standard output captured from the container
     * @param stderr standard error captured from the container
     * @return list of error reports (may be empty)
     */
    public List<ErrorReport> classify(String stdout, String stderr) {
        return logParser.parse(stdout, stderr);
    }

    /**
     * Extracts the primary (first) error report from the output, or {@code null} if clean.
     */
    public ErrorReport primaryError(String stdout, String stderr) {
        List<ErrorReport> errors = logParser.parse(stdout, stderr);
        return errors.isEmpty() ? null : errors.get(0);
    }
}
