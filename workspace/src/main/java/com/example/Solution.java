package com.example;

/**
 * Sample AI-generated solution: sum two integers.
 * This file is intentionally left with a bug (wrong operator) so the
 * pipeline can be demonstrated end-to-end – the LLM should fix it.
 */
public class Solution {

    /**
     * Returns the sum of {@code a} and {@code b}.
     * BUG: uses subtraction instead of addition.
     */
    public int tinhTong(int a, int b) {
        return a - b;   // BUG: should be a + b
    }
}
