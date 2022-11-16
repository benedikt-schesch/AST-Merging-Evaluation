package bad.robot.refactoring.chapter1;

public class HorrorMovie extends Movie{
    private String director;
    public HorrorMovie(String title, int priceCode) {
        super(title, priceCode);
    }

    public String getDirector() {
        return director;
    }

    public void setDirector(String director) {
        this.director = director;
    }
}
