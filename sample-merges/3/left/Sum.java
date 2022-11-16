public class Sum {
    public int sumBetween(int a, int b) {
        if (b <= a) {
            throw new IllegalArgumentException("a must be smaller than b");
        }

        int sum = 1;
        for (int i = a; i < b; i++) {
            sum += i;
        }
        return sum;
    }
}
