package com.example;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * JUnit 5 tests for {@link Solution}.
 * These verify the I/O specification for the "sum two integers" problem.
 */
class SolutionTest {

    private final Solution solution = new Solution();

    @Test
    void testSumPositive() {
        assertEquals(5, solution.tinhTong(2, 3));
    }

    @Test
    void testSumZero() {
        assertEquals(0, solution.tinhTong(0, 0));
    }

    @Test
    void testSumNegative() {
        assertEquals(-5, solution.tinhTong(-2, -3));
    }

    @Test
    void testSumMixed() {
        assertEquals(1, solution.tinhTong(-2, 3));
    }

    @Test
    void testSumLarge() {
        assertEquals(10004, solution.tinhTong(10000, 4));
    }
}
