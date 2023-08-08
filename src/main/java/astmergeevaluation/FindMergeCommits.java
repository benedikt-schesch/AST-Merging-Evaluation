package astmergeevaluation;

import com.opencsv.CSVReaderHeaderAware;
import com.opencsv.exceptions.CsvValidationException;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.checkerframework.checker.lock.qual.GuardSatisfied;
import org.checkerframework.checker.nullness.qual.Nullable;
import org.eclipse.jgit.api.Git;
import org.eclipse.jgit.api.ListBranchCommand;
import org.eclipse.jgit.api.errors.GitAPIException;
import org.eclipse.jgit.internal.storage.file.FileRepository;
import org.eclipse.jgit.lib.ObjectId;
import org.eclipse.jgit.lib.Ref;
import org.eclipse.jgit.lib.Repository;
import org.eclipse.jgit.merge.RecursiveMerger;
import org.eclipse.jgit.revwalk.RevCommit;
import org.eclipse.jgit.revwalk.RevWalk;
import org.eclipse.jgit.revwalk.filter.RevFilter;
import org.eclipse.jgit.transport.CredentialsProvider;
import org.eclipse.jgit.transport.UsernamePasswordCredentialsProvider;
import org.kohsuke.github.GitHub;
import org.kohsuke.github.GitHubBuilder;
import org.plumelib.util.StringsPlume;

/**
 * Given a list of repositories, outputs a list of merge commits. The merge commits may be on the
 * mainline branch, feature branches, and pull requests (both opened and closed).
 *
 * <p>The input is a .csv file, one of whose columns is named "repository" and contains
 * "owner/repo".
 *
 * <p>The output is a set of {@code .csv} files with columns: branch name, merge commit SHA, parent
 * 1 commit SHA, parent 2 commit SHA, base commit SHA, notes. The "notes" column contains "trivial
 * merge", "two initial commits", or is blank.
 *
 * <p>Requires (because JGit requires authentication for cloning and fetching public repositories):
 *
 * <ul>
 *   <li>the existence of a {@code GITHUB_TOKEN} environment variable (GitHub Actions provides
 *       this), or
 *   <li>a {@code .github-personal-access-token} file in your home directory whose first line is
 *       your GitHub username, whose second line is a read-only personal access token, and all other
 *       lines are ignored. (See <a
 *       href="https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token#creating-a-fine-grained-personal-access-token">Creating
 *       a fine-grained personal access token</a>.) Make sure the file is not world-readable.
 * </ul>
 */
// TODO: Why is `@SuppressWarnings` needed?  I commented it out and (with Java 8) got no deprecaton
// warning.
@SuppressWarnings("deprecation") // TODO: add comment here about why needed.
public class FindMergeCommits {

  /** The GitHub repositories to search for merge commits. Each is in the format "owner/repo". */
  List<String> repos;

  /** The output directory. */
  Path outputDir;

  /** Performs GitHub queries and actions. */
  final GitHub gitHub;

  /** The JGit credentials provider. */
  final CredentialsProvider credentialsProvider;

  /**
   * Outputs (TODO: to where?) a list of merge commits from the given repositories.
   *
   * @param args the first element is a .csv file containing GitHub repositories, in "owner/repo"
   *     format, in a column named "repository"
   * @throws IOException if there is trouble reading or writing files
   * @throws GitAPIException if there is trouble running Git commands
   */
  public static void main(String[] args) throws IOException, GitAPIException {
    if (args.length != 2) {
      System.err.printf("Usage: FindMergeCommits <repo-csv-file> <output-dir>%n");
      System.exit(1);
    }

    String inputFileName = args[0];
    // A list of "owner/repo" strings.
    List<String> repos = reposFromCsv(inputFileName);

    String outputDirectoryName = args[1];
    Path outputDir = Paths.get(outputDirectoryName);

    FindMergeCommits fmc = new FindMergeCommits(repos, outputDir);

    fmc.writeMergeCommitsForRepos();
  }

  @Override
  public String toString(@GuardSatisfied FindMergeCommits this) {
    return String.format("FindMergeCommits(%s, %s)", repos, outputDir);
  }

  /**
   * Creates an instance of FindMergeCommits.
   *
   * @param repos a list of GitHub repositories, in "owner/repository" format
   * @param outputDir where to write results; is created if it does not exist
   * @throws IOException if there is trouble reading or writing files
   */
  FindMergeCommits(List<String> repos, Path outputDir) throws IOException {
    this.repos = repos;
    this.outputDir = outputDir;

    this.gitHub =
        GitHubBuilder.fromEnvironment()
            // Use a cache to avoid repeating the same query multiple times (but the OkHttp class
            // is deprecated).
            // .withConnector(new OkHttpConnector(new OkUrlFactory(new
            // OkHttpClient().setCache(cache))))
            .build();

    outputDir.toFile().mkdirs();

    File tokenFile = new File(System.getProperty("user.home"), ".github-personal-access-token");
    String environmentGithubToken = System.getenv("GITHUB_TOKEN");

    String gitHubUsername;
    String gitHubPersonalAccessToken;
    if (tokenFile.exists()) {
      try (@SuppressWarnings("DefaultCharset")
          BufferedReader pwReader = new BufferedReader(new FileReader(tokenFile) /*, UTF_8*/)) {
        gitHubUsername = pwReader.readLine();
        gitHubPersonalAccessToken = pwReader.readLine();
      }
      if (gitHubUsername == null || gitHubPersonalAccessToken == null) {
        System.err.println("File .github-personal-access-token does not contain two lines.");
        System.exit(2);
      }
      this.credentialsProvider =
          new UsernamePasswordCredentialsProvider(gitHubUsername, gitHubPersonalAccessToken);
    } else if (environmentGithubToken != null) {
      this.credentialsProvider =
          new UsernamePasswordCredentialsProvider("Bearer", environmentGithubToken);
    } else {
      System.err.println(
          "Need ~/.gitHubPersonalAccessToken file or GITHUB_TOKEN environment variable.");
      System.exit(3);
      throw new Error("unreachable"); // needed due to javac definite assignment check
    }
  }

  /**
   * Reads a list of repositories from a .csv file, one of whose columns is "repository".
   *
   * @param inputFileName the name of the input .csv file
   * @return a list of repositories
   * @throws IOException if there is trouble reading or writing files
   * @throws GitAPIException if there is trouble running Git commands
   */
  static List<String> reposFromCsv(String inputFileName) throws IOException, GitAPIException {
    List<String> repos = new ArrayList<>();
    try (@SuppressWarnings("DefaultCharset")
            FileReader fr = new FileReader(inputFileName /*, UTF_8*/);
        CSVReaderHeaderAware csvReader = new CSVReaderHeaderAware(fr)) {
      String[] repoColumn;
      while ((repoColumn = csvReader.readNext("repository")) != null) {
        assert repoColumn.length == 1 : "@AssumeAssertion(index): application-specific property";
        repos.add(repoColumn[0]);
      }
    } catch (CsvValidationException e) {
      throw new Error(e);
    }
    return repos;
  }

  /**
   * @throws IOException if there is trouble reading or writing files
   * @throws GitAPIException if there is trouble running Git commands
   */
  void writeMergeCommitsForRepos() throws IOException, GitAPIException {
    System.out.printf("Finding merge commits for %d repositories.%n", repos.size());
    repos.parallelStream().forEach(this::writeMergeCommitsForRepo);
  }

  /**
   * Writes all merge commits for the given repository to a file.
   *
   * @param orgAndRepo the GitHub organization name and repository name, separated by "/"
   */
  void writeMergeCommitsForRepo(String orgAndRepo) {
    String msgPrefix = StringsPlume.rpad("Find merge commits: " + orgAndRepo + " ", 69) + " ";
    System.out.println(msgPrefix + "STARTED");
    try {
      String[] orgAndRepoSplit = orgAndRepo.split("/", -1);
      if (orgAndRepoSplit.length != 2) {
        System.err.printf("repo \"%s\" has wrong number of slashes%n", orgAndRepo);
        System.exit(4);
      }
      writeMergeCommits(orgAndRepoSplit[0], orgAndRepoSplit[1]);
      System.out.println(msgPrefix + "DONE");
    } catch (Throwable e) {
      throw new Error(e);
    }
  }

  /**
   * Writes all merge commits for the given repository to a file.
   *
   * @param orgName the GitHub organization name
   * @param repoName the repository name
   * @throws IOException if there is trouble reading or writing files
   * @throws GitAPIException if there is trouble running Git commands
   */
  void writeMergeCommits(String orgName, String repoName) throws IOException, GitAPIException {
    // This variant includes the organization name in the filename.
    // File outputFile = new File(outputDir.toFile(), orgName + "__" + repoName + ".csv");
    File outputFile = new File(outputDir.toFile(), repoName + ".csv");
    Path outputPath = outputFile.toPath();
    if (Files.exists(outputPath)) {
      // File exists, so there is nothing to do.
      // System.out.printf(
      //     "writeMergeCommits(%s, %s) CACHED; outputFile = %s%n", orgName, repoName, outputFile);
      return;
    }

    String repoDirName =
        "/tmp/"
            + System.getProperty("user.name")
            + "/ast-merge-eval-data/"
            + orgName
            + "__"
            + repoName;
    File repoDirFile = new File(repoDirName);
    repoDirFile.mkdirs();

    // With these assignments, git.branchList() always returns an empty list!
    // So delete and re-clone. :-(
    //      System.out.println("Clone " + repoDirFile + " already exists.");
    //      repo = new FileRepository(repoDirFile);
    //      git = new Git(repo);
    if (repoDirFile.exists()) {
      // Delete the directory.
      try (Stream<Path> pathStream = Files.walk(repoDirFile.toPath())) {
        pathStream.sorted(Comparator.reverseOrder()).map(Path::toFile).forEach(File::delete);
      }
    }

    Git git =
        Git.cloneRepository()
            .setURI("https://github.com/" + orgName + "/" + repoName + ".git")
            .setDirectory(repoDirFile)
            .setCloneAllBranches(true)
            .setCredentialsProvider(credentialsProvider)
            .call();
    FileRepository repo = new FileRepository(repoDirFile);

    makeBranchesForPullRequests(git);

    try (BufferedWriter writer = Files.newBufferedWriter(outputPath, StandardCharsets.UTF_8)) {
      // Write the CSV header
      writer.write("branch_name,merge_commit,parent_1,parent_2,base_commit,notes");
      writer.newLine();

      writeMergeCommitsForBranches(git, repo, orgName, repoName, writer);
    }
  }

  /**
   * Write, to {@code writer}, all the merge commits in all the branches of the given repository.
   *
   * @param git the JGit porcelain
   * @param repo the JGit file system repository
   * @param orgName the organization (owner) name
   * @param repoName the repository name
   * @param writer where to write the merge commits
   * @throws IOException if there is trouble reading or writing files
   * @throws GitAPIException if there is trouble running Git commands
   */
  void writeMergeCommitsForBranches(
      Git git, FileRepository repo, String orgName, String repoName, BufferedWriter writer)
      throws IOException, GitAPIException {
    // github-api.kohsuke.org gives no way to get the commits of a branch, so use JGit instead.
    // (But there is GHRepository.getSHA1(); would that have done the trick?)
    // GHRepository ghRepo = gitHub.getRepository(org + "/" + repo);
    // Map<String,GHBranch> branches = ghRepo.getBranches();

    List<Ref> branches = git.branchList().setListMode(ListBranchCommand.ListMode.ALL).call();
    branches = withoutDuplicateBranches(branches);

    // The SHA ids of the merge commits that have already been output.
    Set<ObjectId> written = new HashSet<>();

    for (Ref branch : branches) {
      writeMergeCommitsForBranch(git, repo, branch, writer, written);
    }
  }

  /**
   * Write, to {@code writer}, all the merge commits in one branch of the given repository.
   *
   * @param git the JGit porcelain
   * @param repo the JGit file system repository
   * @param branch the branch whose commits to output
   * @param writer where to write the merge commits
   * @param written a set of refs that have already been written, to prevent duplicates in the
   *     output
   * @throws IOException if there is trouble reading or writing files
   * @throws GitAPIException if there is trouble running Git commands
   */
  void writeMergeCommitsForBranch(
      Git git, FileRepository repo, Ref branch, BufferedWriter writer, Set<ObjectId> written)
      throws IOException, GitAPIException {

    ObjectId branchId = branch.getObjectId();
    if (branchId == null) {
      throw new Error("no ObjectId for " + branch);
    }
    Iterable<RevCommit> commits = git.log().add(branchId).call();
    for (RevCommit commit : commits) {
      RevCommit[] parents = commit.getParents();
      if (parents.length != 2) {
        // This is not a merge commit.
        continue;
      }

      ObjectId mergeId = commit.toObjectId();
      RevCommit parent1 = parents[0];
      ObjectId parent1Id = parent1.toObjectId();
      RevCommit parent2 = parents[1];
      ObjectId parent2Id = parent2.toObjectId();
      RevCommit mergeBase = getMergeBaseCommit(git, repo, parent1, parent2);
      ObjectId mergeBaseId;
      String notes;

      if (mergeBase == null) {
        // This merge originated from two distinct initial commits.
        notes = "two initial commits";
        mergeBaseId = null;
      } else {
        mergeBaseId = mergeBase.toObjectId();
        if (mergeBaseId.equals(parent1Id) || mergeBaseId.equals(parent2Id)) {
          notes = "trivial merge";
        } else {
          notes = "";
        }
      }

      boolean newMerge = written.add(mergeId);
      // Whenever an already-processed merge is seen, all older merges have also been processed, but
      // don't depend on the order of results from `git log`.
      if (newMerge) {
        // "org_repo,branch_name,merge_commit,parent_1,parent_2,base_commit"
        writer.write(
            String.format(
                "%s,%s,%s,%s,%s,%s",
                branch.getName(),
                ObjectId.toString(mergeId),
                ObjectId.toString(parent1Id),
                ObjectId.toString(parent2Id),
                mergeBaseId == null ? "null" : ObjectId.toString(mergeBaseId),
                notes));
        writer.newLine();
      }
    }
  }

  /**
   * For each remote pull request branch, make a local branch.
   *
   * @param git the JGit porcelain
   * @throws IOException if there is trouble reading or writing files
   * @throws GitAPIException if there is trouble running Git commands
   */
  void makeBranchesForPullRequests(Git git) throws IOException, GitAPIException {
    // No leading "+" in the refspec because all of these updates should be fast-forward.
    git.fetch()
        .setRemote("origin")
        .setRefSpecs("refs/pull/*/head:refs/remotes/origin/pull/*")
        .call();
  }

  /// Git utilities

  /**
   * Returns a list, retaining only the first branch when multiple branches have the same SHA, such
   * as refs/heads/master and refs/remotes/origin/master. The result list has elements in the same
   * order as the argument list.
   *
   * @param branches a list of branches
   * @return the list, with duplicates removed
   */
  @SuppressWarnings("nullness:methodref.return") // method reference, inference failed; likely #979
  List<Ref> withoutDuplicateBranches(List<Ref> branches) {
    return new ArrayList<>(
        branches.stream()
            .collect(Collectors.toMap(Ref::getObjectId, p -> p, (p, q) -> p, LinkedHashMap::new))
            .values());
  }

  /**
   * Given two commits, return their merge base commit. It is the nearest ancestor of both commits.
   * If there is none (because the two commits have different initial commits!), then this returns
   * null.
   *
   * <p>This always returns an existing commit (or null), never a synthetic one. When a criss-cross
   * merge exists in the history, this outputs an arbitrary one of the best merge bases.
   *
   * @param git the JGit porcelain
   * @param repo the JGit repository
   * @param commit1 the first parent commit
   * @param commit2 the second parent commit
   * @return the merge base of the two commits, or null if none exists
   */
  @Nullable RevCommit getMergeBaseCommit(
      Git git, Repository repo, RevCommit commit1, RevCommit commit2) {
    if (commit1.equals(commit2)) {
      throw new Error(
          String.format(
              "Same commit passed twice: getMergeBaseCommit(%s, \"%s\", \"%s\")",
              repo, commit1, commit2));
    }

    try {
      List<RevCommit> history1 = new ArrayList<>();
      git.log().add(commit1).call().forEach(history1::add);
      List<RevCommit> history2 = new ArrayList<>();
      git.log().add(commit2).call().forEach(history2::add);

      if (history1.contains(commit2)) {
        return commit2;
      } else if (history2.contains(commit1)) {
        return commit1;
      }

      Collections.reverse(history1);
      Collections.reverse(history2);
      int minLength = Math.min(history1.size(), history2.size());
      int commonPrefixLength = -1;
      for (int i = 0; i < minLength; i++) {
        if (!history1.get(i).equals(history2.get(i))) {
          commonPrefixLength = i;
          break;
        }
      }

      if (commonPrefixLength == 0) {
        // Sometimes, a repository contains multiple initial commits.  (Or, they may result from a
        // mistake while squashing commits.)  Ignore merges that involve two initial commits.
        return null;
      } else if (commonPrefixLength == -1) {
        throw new Error(
            String.format(
                "Histories are equal for getMergeBaseCommit(%s, \"%s\", \"%s\")",
                repo, commit1, commit2));
      }

      return history1.get(commonPrefixLength - 1);
    } catch (Exception e) {
      throw new Error(e);
    }
  }

  // This doesn't work; I don't know why.
  /**
   * Given two commits, return their merge base commit. It is the nearest ancestor of both commits.
   *
   * <p>Since only two commits are passed in, this always returns an existing commit, never a
   * synthetic one. When a criss-cross merge exists in the history, this outputs an arbitrary one of
   * the best merge bases.
   *
   * @param git the JGit porcelain
   * @param repo the JGit repository
   * @param commit1 the first parent commit
   * @param commit2 the second parent commit
   * @return the merge base of the two commits
   */
  RevCommit getMergeBaseCommit2(Git git, Repository repo, RevCommit commit1, RevCommit commit2) {
    try {
      RevWalk walk = new RevWalk(repo);
      walk.setRevFilter(RevFilter.MERGE_BASE);
      walk.markStart(walk.parseCommit(commit1));
      walk.markStart(walk.parseCommit(commit2));
      ArrayList<RevCommit> baseCommits = new ArrayList<>();
      RevCommit c;
      while ((c = walk.next()) != null) {
        baseCommits.add(c);
      }
      if (baseCommits.size() == 1) {
        return baseCommits.get(0);
      }
      throw new Error(
          String.format(
              "Wrong number of base commits for getMergeBaseCommit(%s, \"%s\", \"%s\"): %s",
              repo, commit1, commit2, baseCommits));
    } catch (IOException e) {
      throw new Error(e);
    }
  }

  // This doesn't work; I don't know why.
  /**
   * Given two commits, return their merge base commit. It is the nearest ancestor of both commits.
   *
   * <p>Since only two commits are passed in, this always returns an existing commit, never a
   * synthetic one. When a criss-cross merge exists in the history, this outputs an arbitrary one of
   * the best merge bases.
   *
   * @param git the JGit porcelain
   * @param repo the JGit repository
   * @param commit1 the first parent commit
   * @param commit2 the second parent commit
   * @return the merge base of the two commits
   */
  RevCommit getMergeBaseCommit3(Git git, Repository repo, RevCommit commit1, RevCommit commit2) {
    try {
      Constructor<RecursiveMerger> constructor =
          RecursiveMerger.class.getDeclaredConstructor(Repository.class);
      constructor.setAccessible(true);
      Method getBaseCommitMethod =
          RecursiveMerger.class.getDeclaredMethod(
              "getBaseCommit", RevCommit.class, RevCommit.class);
      getBaseCommitMethod.setAccessible(true);

      RecursiveMerger recursiveMerger = constructor.newInstance(repo);
      RevCommit baseCommit =
          (RevCommit) getBaseCommitMethod.invoke(recursiveMerger, commit1, commit2);
      if (baseCommit == null) {
        throw new Error(
            String.format(
                "null baseCommit for getMergeBaseCommit(%s, \"%s\", \"%s\")",
                repo, commit1, commit2));
      }
      return baseCommit;
    } catch (Exception e) {
      throw new Error(e);
    }
  }
}
