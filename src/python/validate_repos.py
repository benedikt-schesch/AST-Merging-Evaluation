#!/usr/bin/env python3
"""Tests the HEAD of a repo and validates it if the test passes.

usage: python3 validate_repos.py --repos_csv <repos.csv>
                                 --output_path <valid_repos.csv>

Input: a csv of repos.  It must contain a header, one of whose columns is "repository".
That column contains "ORGANIZATION/REPO" for a GitHub repository.
Output:  the rows of the input for which the head of the default branch passes tests.
"""
import subprocess
import shutil
import os
import multiprocessing
import argparse
from pathlib import Path
import sys
from functools import partialmethod
from enum import Enum
from typing import Tuple

from tqdm import tqdm
import pandas as pd
import git.repo

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore

WORKDIR = ".workdir/"
TIMEOUT_TESTING = 30 * 60  # 30 minutes
REPO_SETUP_SCRIPTS = "repo_setup_scripts"
TEST_STATE = Enum(
    "TEST_STATE",
    [
        "Tests_passed",
        "Tests_failed",
        "Failure_git_checkout",
        "Failure_git_clone",
        "Failure_test_exception",
        "Tests_timedout",
        "Failure_repo_setup_script_exception",
        "Not_tested",
    ],
)


def clone_repo(repo_name: str) -> git.repo.Repo:
    """Clones a repository, or runs `git fetch` if it is already cloned.
    Args:
        repo_name (str): The name of the repository to be cloned
    Returns:
        git.repo.Repo: The repository
    """
    repo_dir = os.path.join("repos/", repo_name)
    if os.path.isdir(repo_dir):
        repo = git.repo.Repo(repo_dir)
    else:
        # ":@" in URL ensures that we are not prompted for login details
        # for the repos that are now private.
        print(repo_name, " : Cloning repo")
        git_url = "https://:@github.com/" + repo_name + ".git"
        repo = git.repo.Repo.clone_from(git_url, repo_dir)
        print(repo_name, " : Finished cloning")
    try:
        repo.remote().fetch()
        repo.submodule_update()
    except Exception as e:
        print(repo_name, "Exception during cloning. Exception:\n", e)
        raise
    return repo


def repo_test(repo_dir_copy: str, timeout: int) -> Tuple[TEST_STATE, str]:
    """Returns the result of trying 3 times to run run_repo_tests.sh on the given working copy.
    If one test passes then the entire test is marked as passed.
    If one test timeouts then the entire test is marked as timeout.
    Args:
        repo_dir_copy (str): The path of the working copy (the clone).
        timeout (int): Test Timeout limit.
    Returns:
        TEST_STATE: The result of the test.
        str: explanation. The explanation of the result.
    """
    explanation = ""
    rc = 1  # Failure
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
        if rc == 0:  # Success
            return TEST_STATE.Tests_passed, explanation
        if rc == 128:
            return TEST_STATE.Tests_timedout, explanation
    return TEST_STATE.Tests_failed, explanation  # Failure


def write_cache(status: TEST_STATE, explanation: str, cache_file: str):
    """Writes the result of the test to a cache file.
    Args:
        status (TEST_STATE): The result of the test.
        explanation (str): The explanation of the result.
        cache_file (str): The path of the cache file.
    """
    with open(cache_file + ".txt", "w") as f:
        f.write(status.name)
    with open(cache_file + "_explanation.txt", "w") as f:
        f.write(explanation)


def read_cache(cache_file: str) -> Tuple[TEST_STATE, str]:
    """Reads the result of the test from a cache file.
    Args:
        cache_file (str): The path of the cache file.
    Returns:
        TEST_STATE: The result of the test.
        str: The explanation of the result.
    """
    with open(cache_file + ".txt", "r") as f:
        status_name = f.readline().strip()
        status = TEST_STATE[status_name]
    with open(cache_file + "_explanation.txt", "r") as f:
        explanation = "".join(f.readlines())
    return status, explanation


def del_rw(action, name, exc):
    """Delete read-only files. Some repos contain read-only
    files which cannot be deleted.
    Args:
        action (str): The action to be taken.
        name (str): The name of the file.
        exc (str): The exception.
    """
    subprocess.call(["chmod", "-R", "777", name])
    shutil.rmtree(name, ignore_errors=True)


def commit_pass_test(  # pylint: disable=too-many-statements
    repo_name: str, commit: str, diagnostic: str, cache: str
) -> TEST_STATE:
    """Tests a commit of a repository.
    Args:commit_pass_test
        repo_name (str): The name of the repository.
        commit (str): The commit to be tested.
        diagnostic (str): A string printed in diagnostics.
        cache (str): The path of the cache directory.
    Returns:
        TEST_STATE: The result of the test.
    """
    print(repo_name, commit, ": Started testing commit")

    repo_dir = os.path.join("repos/", repo_name)
    target_file = os.path.join(cache, repo_name.replace("/", "_") + "_" + str(commit))
    # Check if result is cached
    if os.path.isfile(target_file + ".txt"):
        status, _ = read_cache(target_file)
        print(
            repo_name,
            commit,
            ": Cached result from " + target_file + ".txt: " + status.name,
        )
        return status

    status = TEST_STATE.Not_tested
    explanation = "Process started"
    write_cache(status, explanation, target_file)

    pid = str(multiprocessing.current_process().pid)
    work_dir = os.path.join(WORKDIR, pid)
    repo_dir_copy = os.path.join(work_dir, "repo")
    if os.path.isdir(work_dir):
        shutil.rmtree(work_dir, onerror=del_rw)
    try:
        try:
            _ = clone_repo(repo_name)
        except Exception as e:
            status = TEST_STATE.Failure_git_clone
            explanation = str(e)
            raise

        shutil.copytree(repo_dir, repo_dir_copy)
        repo = git.repo.Repo(repo_dir_copy)
        try:
            repo.remote().fetch()
            repo.git.checkout(commit, force=True)
            repo.submodule_update()
        except Exception as e:
            status = TEST_STATE.Failure_git_checkout
            explanation = f"commit_pass_test({str}, {commit}, {diagnostic})\n" + str(e)
            raise
        setup_script_path = os.path.join(
            REPO_SETUP_SCRIPTS, repo_name.split("/")[1] + ".sh"
        )
        if os.path.isfile(setup_script_path):
            try:
                print(repo_name, ": Running setup script for repo")
                subprocess.run(
                    [
                        setup_script_path,
                        repo_dir_copy,
                    ],
                    capture_output=True,
                )
                print(repo_name, commit, ": Finished running setup script for repo")
            except Exception as e:
                print(
                    repo_name, commit, ": Setup script failed with exception:", str(e)
                )
                status = TEST_STATE.Failure_repo_setup_script_exception
                explanation = str(e)
                raise
        try:
            status, explanation = repo_test(repo_dir_copy, TIMEOUT_TESTING)
        except Exception as e:
            status = TEST_STATE.Failure_test_exception
            explanation = str(e)
            raise
    except Exception:
        pass
    write_cache(status, explanation, target_file)
    print(repo_name, commit, ": Finished testing commit: ", status.name)
    if os.path.isdir(work_dir):
        # Remove all permision restrictions from work_dir
        shutil.rmtree(work_dir, onerror=del_rw)
    return status


def head_passes_tests(repo_info: pd.Series, cache: str) -> TEST_STATE:
    """Checks if the head of main passes test.
    Args:
        repo_info (pd.Series): The information of the repository.
        cache (str): The path of the cache directory.
    Returns:
        TEST_STATE: The result of the test.
    """
    repo_name = repo_info["repository"]
    print(repo_name, ": Started head_passes_tests")

    status = commit_pass_test(
        repo_name, repo_info["Validation hash"], "Validation hash", cache
    )

    print(
        repo_name,
        ": Finished head_passes_tests, result:",
        status.name,
    )
    return status


if __name__ == "__main__":
    Path(WORKDIR).mkdir(parents=True, exist_ok=True)
    Path("repos").mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_csv_with_hashes", type=str)
    parser.add_argument("--output_path", type=str)
    parser.add_argument("--cache_dir", type=str, default="cache/test_result/")
    args = parser.parse_args()

    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.repos_csv_with_hashes, index_col="idx")

    print("validate_repos: Started Testing")
    cpu_count = os.cpu_count() or 1
    processes_used = cpu_count - 2 if cpu_count > 3 else cpu_count
    with multiprocessing.Pool(processes=processes_used) as pool:
        results = [
            pool.apply_async(head_passes_tests, args=((v[1], args.cache_dir)))
            for v in df.iterrows()
        ]
        for result in tqdm(results, total=len(results)):
            try:
                return_value = result.get(2 * TIMEOUT_TESTING)
            except multiprocessing.TimeoutError:
                print("Timeout")
    print("validate_repos: Finished Testing")

    print("validate_repos: Building Output")
    out = []
    valid_repos_mask = [
        head_passes_tests(row, args.cache_dir) == TEST_STATE.Tests_passed
        for _, row in tqdm(df.iterrows(), total=len(df))
    ]
    out = df[valid_repos_mask]
    print("validate_repos: Finished Building Output")
    print("validate_repos: Number of valid repos:", len(out))
    if len(out) == 0:
        sys.exit(1)
    out.to_csv(args.output_path, index_label="idx")
    print("validate_repos: Done")
