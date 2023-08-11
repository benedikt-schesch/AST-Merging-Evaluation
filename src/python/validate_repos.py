#!/usr/bin/env python3
"""Tests the HEAD of a repo and validates it if the test passes.

usage: python3 validate_repos.py --repos_csv_with_hashes <repos_csv_with_hashes.csv>
                                 --output_path <valid_repos.csv>
                                 --cache_dir <cache_dir>

Input: a csv of repos.  It must contain a header, one of whose columns is "repository".
That column contains "ORGANIZATION/REPO" for a GitHub repository. The csv must also
contain a column "Validation hash" which contains a commit hash for the repo that
will be tested. Cache_dir is the directory where the cache will be stored.
Output:  the rows of the input for which the head of the default branch passes tests.
"""
import multiprocessing
import os
import argparse
from pathlib import Path
import sys
from functools import partialmethod
from typing import Tuple
from repo import Repository, TEST_STATE, REPOS_PATH
from cache_utils import (
    get_cache_lock,
    get_cache_path,
    isin_cache,
    load_cache,
)

from tqdm import tqdm
import pandas as pd
import git.repo

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore


TIMEOUT_TESTING = 60 * 30  # 30 minutes


def clone_repo(repo_name: str) -> git.repo.Repo:
    """Clones a repository, or runs `git fetch` if it is already cloned.
    Args:
        repo_name (str): The name of the repository to be cloned
    """
    repo_dir = REPOS_PATH / repo_name
    if os.path.isdir(repo_dir):
        repo = git.repo.Repo(repo_dir)
    else:
        # ":@" in URL ensures that we are not prompted for login details
        # for the repos that are now private.
        os.environ["GIT_TERMINAL_PROMPT"] = "0"
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


def head_passes_tests(args: Tuple[pd.Series, Path]) -> TEST_STATE:
    """Checks if the head of main passes test.
    Args:
        args (Tuple[pd.Series,Path]): A tuple containing the repository info and the cache path.
    Returns:
        TEST_STATE: The result of the test.
    """
    repo_info, cache = args
    repo_name = repo_info["repository"]
    print(repo_name, ": head_passes_tests : started")

    repo = Repository(repo_name, cache_prefix=cache)
    test_result = repo.checkout_and_test_cached(
        repo_info["Validation hash"], timeout=TIMEOUT_TESTING, n_restarts=3
    )
    return test_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_csv_with_hashes", type=Path)
    parser.add_argument("--output_path", type=Path)
    parser.add_argument("--cache_dir", type=Path, default="cache/")
    args = parser.parse_args()

    Path(REPOS_PATH).mkdir(parents=True, exist_ok=True)
    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.repos_csv_with_hashes, index_col="idx")

    print("validate_repos: Starting cloning repos")
    cpu_count = os.cpu_count() or 1
    processes_used = cpu_count - 2 if cpu_count > 3 else cpu_count
    repos_to_clone = []
    with multiprocessing.Pool(processes=processes_used) as pool:
        results = [
            pool.apply_async(clone_repo, args=(row["repository"],))
            for _, row in df.iterrows()
        ]
        for result in tqdm(results, total=len(results)):
            try:
                return_value = result.get(10 * 60)
            except Exception as e:
                print("Couldn't clone repo", e)
    print("validate_repos: Finished cloning repos")

    if os.path.exists(args.output_path):
        print("validate_repos: Output file already exists. Exiting.")
        sys.exit(0)

    print("validate_repos: Started Testing")
    cpu_count = os.cpu_count() or 1
    processes_used = cpu_count - 2 if cpu_count > 3 else cpu_count
    arguments = [(v, args.cache_dir) for _, v in df.iterrows()]
    with multiprocessing.Pool(processes=processes_used) as pool:
        result = list(
            tqdm(pool.imap(head_passes_tests, arguments), total=len(arguments))
        )
    print("validate_repos: Finished Testing")

    print("validate_repos: Building Output")
    out = []
    valid_repos_mask = [i == TEST_STATE.Tests_passed for i in result]
    out = df[valid_repos_mask]
    print("validate_repos: Finished Building Output")

    print("validate_repos: Number of valid repos:", len(out), "out of", len(df))
    if len(out) == 0:
        raise Exception("No valid repos found")
    out.to_csv(args.output_path, index_label="idx")
    print("validate_repos: Done")
