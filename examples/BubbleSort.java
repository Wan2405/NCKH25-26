public class BubbleSort {
    public static int[] sort(int[] arr) {
        int n = arr.length;
        int[] result = arr.clone();
        for (int i = 0; i < n - 1; i++) {
            for (int j = 0; j < n - i - 1; j++) {
                if (result[j] > result[j + 1]) {
                    int temp = result[j];
                    result[j] = result[j + 1];
                    result[j + 1] = temp;
                }
            }
        }
        return result;
    }

    public static void main(String[] args) {
        int[] arr = {64, 34, 25, 12, 22, 11, 90};
        int[] sorted = sort(arr);
        for (int val : sorted) {
            System.out.print(val + " ");
        }
        System.out.println();
    }
}
