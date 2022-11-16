package bad.robot.refactoring.chapter1;

public class ComedyMovie extends Movie {
    private String mainDirector;

    public ComedyMovie(String title, int priceCode) {
        super(title, priceCode);
    }

    public String getDirector() {
        return mainDirector;
    }

    public void setDirector(String director) {
        this.mainDirector = director;
    }
}
