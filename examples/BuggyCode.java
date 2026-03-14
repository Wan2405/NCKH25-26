// This file intentionally has bugs for testing the analyzer
public class BuggyCode {
    public static void main(String[] args) {
        int[] numbers = {1, 2, 3, 4, 5};

        // Bug: ArrayIndexOutOfBoundsException - accessing index 5
        for (int i = 0; i <= numbers.length; i++) {
            System.out.println(numbers[i]);
        }

        // Bug: NullPointerException
        String text = null;
        System.out.println(text.length());
    }
}
