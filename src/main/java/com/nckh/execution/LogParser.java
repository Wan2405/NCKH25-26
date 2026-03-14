package com.nckh.execution;

import com.nckh.model.ErrorReport;
import com.nckh.model.ErrorReport.ErrorType;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Parses raw stdout/stderr captured from Docker container execution and extracts
 * structured information: compilation errors, runtime exceptions, and JUnit results.
 *
 * <p>The parser targets output produced by {@code mvn clean test} using the Maven
 * Surefire plugin with JUnit 5.
 */
public class LogParser {

    private static final Logger log = LoggerFactory.getLogger(LogParser.class);

    // javac / Maven compiler error: "Solution.java:[12,5] error: cannot find symbol"
    private static final Pattern COMPILE_ERROR_PATTERN =
            Pattern.compile("(?m)^.*?(\\w+\\.java):\\[?(\\d+)[,\\d]*\\]?\\s+error:\\s+(.+)$");

    // Maven compiler plugin output: "[ERROR] /path/to/File.java:[12,5] cannot find symbol"
    private static final Pattern MAVEN_COMPILE_ERROR_PATTERN =
            Pattern.compile("(?m)^\\[ERROR\\].*?([A-Za-z0-9_]+\\.java):\\[(\\d+),\\d+\\]\\s+(.+)$");

    // Runtime exception in stack trace: "java.lang.NullPointerException at Foo.bar(Foo.java:42)"
    private static final Pattern RUNTIME_EXCEPTION_PATTERN =
            Pattern.compile("(?m)^(\\S+Exception|\\S+Error):\\s*(.*)$");

    private static final Pattern STACK_TRACE_AT_PATTERN =
            Pattern.compile("(?m)^\\s+at\\s+([\\w.$]+)\\.([\\w<>$]+)\\(([\\w.]+\\.java):(\\d+)\\)");

    // Surefire summary: "Tests run: 5, Failures: 1, Errors: 0, Skipped: 0"
    private static final Pattern SUREFIRE_SUMMARY_PATTERN =
            Pattern.compile("Tests run:\\s*(\\d+),\\s*Failures:\\s*(\\d+),\\s*Errors:\\s*(\\d+),\\s*Skipped:\\s*(\\d+)");

    // Missing dependency: "[ERROR] ... Could not resolve dependencies ..."
    private static final Pattern MISSING_DEPENDENCY_PATTERN =
            Pattern.compile("(?m)Could not resolve dependencies|Cannot resolve artifact|Artifact.*not found");

    /**
     * Parses the combined build output and returns a list of {@link ErrorReport} objects.
     *
     * @param stdout standard output from the container
     * @param stderr standard error from the container
     * @return list of parsed errors; empty list if the build succeeded with no errors
     */
    public List<ErrorReport> parse(String stdout, String stderr) {
        String combined = (stdout == null ? "" : stdout) + "\n" + (stderr == null ? "" : stderr);
        List<ErrorReport> reports = new ArrayList<>();

        // 1. Check for missing dependency issues first
        if (MISSING_DEPENDENCY_PATTERN.matcher(combined).find()) {
            ErrorReport er = new ErrorReport(
                    ErrorType.MISSING_DEPENDENCY, null, null,
                    "missing_dependency", "Could not resolve one or more Maven dependencies");
            er.setRawOutput(combined);
            reports.add(er);
            return reports; // dependency errors overshadow compile errors
        }

        // 2. Parse compilation errors
        reports.addAll(parseCompileErrors(combined));

        // 3. Parse runtime exceptions (only if no compile errors to avoid noise)
        if (reports.isEmpty()) {
            reports.addAll(parseRuntimeExceptions(combined));
        }

        // 4. Parse JUnit test failures
        reports.addAll(parseTestFailures(combined));

        log.debug("LogParser found {} error report(s)", reports.size());
        return reports;
    }

    /**
     * Extracts the total/passed/failed test counts from Surefire output.
     *
     * @param output combined stdout+stderr
     * @return int array: [total, passed, failed]; {0, 0, 0} if not found
     */
    public int[] parseTestCounts(String output) {
        if (output == null) return new int[]{0, 0, 0};
        Matcher m = SUREFIRE_SUMMARY_PATTERN.matcher(output);
        int total = 0, failures = 0, errors = 0, skipped = 0;
        while (m.find()) {
            // accumulate across multiple test classes
            total    += Integer.parseInt(m.group(1));
            failures += Integer.parseInt(m.group(2));
            errors   += Integer.parseInt(m.group(3));
            skipped  += Integer.parseInt(m.group(4));
        }
        int failed  = failures + errors;
        int passed  = total - failed - skipped;
        return new int[]{total, Math.max(0, passed), failed};
    }

    // ---- private helpers ----

    private List<ErrorReport> parseCompileErrors(String text) {
        List<ErrorReport> list = new ArrayList<>();

        // Try Maven-style "[ERROR] .../File.java:[line,col] message"
        Matcher m = MAVEN_COMPILE_ERROR_PATTERN.matcher(text);
        while (m.find() && list.size() < 20) {
            ErrorReport er = new ErrorReport(
                    ErrorType.COMPILE_ERROR,
                    m.group(1),
                    Integer.parseInt(m.group(2)),
                    categorizeCompileMessage(m.group(3)),
                    m.group(3).trim());
            list.add(er);
        }

        // Fallback: standard javac-style "File.java:[12,5] error: …"
        if (list.isEmpty()) {
            m = COMPILE_ERROR_PATTERN.matcher(text);
            while (m.find() && list.size() < 20) {
                ErrorReport er = new ErrorReport(
                        ErrorType.COMPILE_ERROR,
                        m.group(1),
                        Integer.parseInt(m.group(2)),
                        categorizeCompileMessage(m.group(3)),
                        m.group(3).trim());
                list.add(er);
            }
        }
        return list;
    }

    private List<ErrorReport> parseRuntimeExceptions(String text) {
        List<ErrorReport> list = new ArrayList<>();
        Matcher m = RUNTIME_EXCEPTION_PATTERN.matcher(text);
        while (m.find() && list.size() < 10) {
            String exType = m.group(1);
            String msg    = m.group(2).trim();

            // Try to find source location from the first "at" line
            String file = null;
            Integer line = null;
            Matcher at = STACK_TRACE_AT_PATTERN.matcher(text.substring(m.start()));
            if (at.find()) {
                file = at.group(3);
                line = Integer.parseInt(at.group(4));
            }

            ErrorReport er = new ErrorReport(
                    ErrorType.RUNTIME_EXCEPTION, file, line,
                    exType, msg.isEmpty() ? exType : msg);
            list.add(er);
        }
        return list;
    }

    private List<ErrorReport> parseTestFailures(String text) {
        List<ErrorReport> list = new ArrayList<>();
        // Surefire prints "FAILED" next to the test method name
        Pattern failPattern = Pattern.compile("(?m)^\\[ERROR\\]\\s+(\\S+)\\s+--\\s+Time elapsed.*FAILED!?(.*)$");
        Matcher m = failPattern.matcher(text);
        while (m.find() && list.size() < 20) {
            String testRef = m.group(1);
            // Extract simple class name
            String[] parts = testRef.split("\\.");
            String className = parts.length > 0 ? parts[parts.length - 1] : testRef;
            ErrorReport er = new ErrorReport(
                    ErrorType.TEST_FAILURE, className + ".java", null,
                    "assertion_failure",
                    "Test failed: " + testRef + " " + m.group(2).trim());
            list.add(er);
        }
        return list;
    }

    private String categorizeCompileMessage(String msg) {
        if (msg == null) return "compile_error";
        String lower = msg.toLowerCase();
        if (lower.contains("cannot find symbol"))     return "missing_import";
        if (lower.contains("cannot be applied"))      return "wrong_method_signature";
        if (lower.contains("incompatible types"))     return "type_mismatch";
        if (lower.contains("missing return"))         return "missing_return";
        if (lower.contains("duplicate class"))        return "duplicate_class";
        if (lower.contains("reached end of file"))    return "syntax_error";
        if (lower.contains("';' expected"))           return "syntax_error";
        return "compile_error";
    }
}
