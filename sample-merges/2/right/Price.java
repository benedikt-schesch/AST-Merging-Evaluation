package bad.robot.refactoring.chapter1;

public abstract class Price {
    abstract int getPriceCode();

    abstract double getCharge(int daysRented);

    int getPointsOfFrequentRenters(int daysRented) {
        return 1;
    }
}
