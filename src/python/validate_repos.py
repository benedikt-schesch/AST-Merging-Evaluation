#!/usr/bin/env python3
"""Tests the HEAD of a repo and validates it if the test passes.

usage: python3 validate_repos.py --repos_csv <repos.csv>
                                 --output_path <valid_repos.csv>

Input: a csv of repos.  It must contain a header, one of whose columns is "repository".
That column contains "ORGANIZATION/REPO" for a GitHub repository.
Output:  the rows of the input for which the head of main passes tests.
"""

import subprocess
import shutil
import os
import multiprocessing
import argparse
from pathlib import Path

from tqdm import tqdm
import pandas as pd
import git

CACHE = "cache/repos_result/"
WORKDIR = ".workdir/"
TIMEOUT_TESTING = 30 * 60  # 30 minutes


def clone_repo(repo_name):
    """Clones a repository, or runs `git fetch` it if it is already cloned.
    Args:
        repo_name (str): The name of the repository to be cloned
    Returns:
        The repository
    """
    repo_dir = "repos/" + repo_name
    if os.path.isdir(repo_dir):
        repo = git.Repo(repo_dir)
    else:
        # ":@" in URL ensures that we are not prompted for login details
        # for the repos that are now private.
        git_url = "https://:@github.com/" + repo_name + ".git"
        repo = git.Repo.clone_from(git_url, repo_dir)
    try:
        repo.remote().fetch()
    except Exception as e:
        print(repo_name, "Exception during cloning. Exception:\n", e)
        pass
    return repo


def repo_test(repo_dir_copy, timeout):
    """Returns the return code of trying 3 times to run run_repo_tests.sh on the given working copy.
    If one test passes then the entire test is marked as passed.
    If one test timeouts then the entire test is marked as timeout.
    Args:
        repo_dir_copy (str): The path of the working copy (the clone).
        timeout (int): Test Timeout limit.
    Returns:
        int: The test value.
    """
    for i in range(3):
        command = [
            "src/scripts/run_repo_tests.sh",
            repo_dir_copy,
        ]
        p = subprocess.run(  # pylint: disable=consider-using-with
            command,
            timeout=timeout,
            capture_output=True,
        )
        rc = p.returncode
        stdout = p.stdout.decode("utf-8")
        stderr = p.stderr.decode("utf-8")
        explanation = (
            "Run Command: "
            + " ".join(command)
            + "\nstdout:\n"
            + stdout
            + "\nstderr:\n"
            + stderr
        )
        if rc in (0, 124):  # Success or Timeout
            return rc, explanation
    return 1, explanation  # Failure


def head_passes_tests(arg):
    """Checks if the head of main passes test.
    Args:
        arg (str): Information regarding that repo.
    Returns:
        int: 0 if the repo is valid (main head passes tests)
    """
    _, row = arg
    repo_name = row["repository"]
    print(repo_name, ": Started head_passes_tests")
    result_interpretable = {0: "Valid", 1: "Not Valid", 124: "Not Valid Timeout"}

    repo_dir = "repos/" + repo_name
    target_file = CACHE + repo_name.replace("/", "_") + ".csv"

    df = pd.DataFrame({"test": [1]})
    pid = str(multiprocessing.current_process().pid)
    repo_dir_copy = WORKDIR + pid + "/repo"
    if os.path.isdir(repo_dir_copy):
        shutil.rmtree(repo_dir_copy)
    try:
        print(repo_name, ": Cloning repo")
        _ = clone_repo(repo_name)
        print(repo_name, ": Finished cloning")

        # Check if result is cached
        if os.path.isfile(target_file):
            df = pd.read_csv(target_file)
            print(
                repo_name,
                ": Done, result is cached in "
                + target_file
                + ": "
                + result_interpretable[df.iloc[0]["test"]],
            )
            return df.iloc[0]["test"] == 0

        print(repo_name, ": Testing")
        shutil.copytree(repo_dir, repo_dir_copy)
        repo = git.Repo(repo_dir_copy)
        repo.remote().fetch()
        repo.git.checkout(row["Validation hash"], force=True)
        rc, explanation = repo_test(repo_dir_copy, TIMEOUT_TESTING)
        df = pd.DataFrame({"test": [rc]})
        print(repo_name, ": Finished testing, result =", rc)
    except Exception as e:
        print(repo_name, ": Finished testing, result = exception, Exception:\n", e)
    df.to_csv(target_file)
    if os.path.isdir(repo_dir_copy):
        shutil.rmtree(repo_dir_copy)
    print(
        repo_name,
        "Finished head_passes_tests, result : ",
        result_interpretable[df.iloc[0]["test"]],
    )
    return df.iloc[0]["test"] == 0


if __name__ == "__main__":
    Path("repos").mkdir(parents=True, exist_ok=True)
    Path(CACHE).mkdir(parents=True, exist_ok=True)
    Path(WORKDIR).mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_csv", type=str)
    parser.add_argument("--output_path", type=str)
    args = parser.parse_args()
    df = pd.read_csv(args.repos_csv)

    print("validate_repos: Started Testing")
    with multiprocessing.Pool(processes=int(os.cpu_count() * 0.75)) as pool:
        r = list(
            tqdm(
                pool.imap(head_passes_tests, df.iterrows()),
                total=len(df),
            )
        )
    print("validate_repos: Finished Testing")

    print("validate_repos: Building Output")
    out = []
    for repo_idx, row in tqdm(df.iterrows(), total=len(df)):
        if head_passes_tests((repo_idx, row)):
            out.append(row)
    print("validate_repos: Finished Building Output")
    out = pd.DataFrame(out)
    out.to_csv(args.output_path)
    print("validate_repos: Number of valid repos:", len(out))
    print("validate_repos: Done")
