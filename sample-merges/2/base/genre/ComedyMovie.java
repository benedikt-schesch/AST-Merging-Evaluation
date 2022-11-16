package bad.robot.refactoring.chapter1;

public class ComedyMovie extends Movie {
    private String director;

    public ComedyMovie(String title, int priceCode) {
        super(title, priceCode);
    }

    public String getDirector() {
        return director;
    }

    public void setDirector(String director) {
        this.director = director;
    }
}
