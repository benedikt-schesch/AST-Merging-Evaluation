package bad.robot.refactoring.chapter1;

public class HorrorMovie extends Movie{
    private String mainDirector;
    public HorrorMovie(String title, int priceCode) {
        super(title, priceCode);
    }

    public String getDirector() {
        return mainDirector;
    }

    public void setDirector(String director) {
        this.mainDirector = director;
    }
}
