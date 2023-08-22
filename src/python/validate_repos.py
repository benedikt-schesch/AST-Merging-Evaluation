#!/usr/bin/env python3
"""Tests the HEAD of a repo and validates it if the test passes.

usage: python3 validate_repos.py --repos_csv_with_hashes <repos_csv_with_hashes.csv>
                                 --output_path <valid_repos.csv>
                                 --cache_dir <cache_dir>

Input: a csv of repos.  It must contain a header, one of whose columns is "repository".
That column contains "ORGANIZATION/REPO" for a GitHub repository. The csv must also
contain a column "head hash" which contains a commit hash that will be tested. 
Cache_dir is the directory where the cache will be stored.
Output: the rows of the input for which the commit at the validation hash passes tests.
"""
import multiprocessing
import os
import argparse
from pathlib import Path
import sys
from functools import partialmethod
from typing import Tuple
from repo import Repository, TEST_STATE

from tqdm import tqdm
import pandas as pd
from write_head_hashes import compute_num_cpus_used, clone_repo

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore


TIMEOUT_TESTING = 60 * 30  # 30 minutes, in seconds.


def head_passes_tests(args: Tuple[pd.Series, Path]) -> TEST_STATE:
    """Checks if the head of main passes test.
    Args:
        args (Tuple[pd.Series,Path]): A tuple containing the repository info and the cache path.
    Returns:
        TEST_STATE: The result of the test.
    """
    repo_info, cache = args
    repo_slug = repo_info["repository"]
    print(repo_slug, ": head_passes_tests : started")

    repo = Repository(repo_slug, cache_prefix=cache)
    test_result = repo.checkout_and_test_cached(
        repo_info["head hash"], timeout=TIMEOUT_TESTING, n_restarts=3
    )
    return test_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_csv_with_hashes", type=Path)
    parser.add_argument("--output_path", type=Path)
    parser.add_argument("--cache_dir", type=Path, default="cache/")
    args = parser.parse_args()

    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.repos_csv_with_hashes, index_col="idx")

    print("validate_repos: Starting cloning repos")
    with multiprocessing.Pool(processes=compute_num_cpus_used()) as pool:
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
    head_passes_tests_arguments = [(v, args.cache_dir) for _, v in df.iterrows()]
    with multiprocessing.Pool(processes=compute_num_cpus_used()) as pool:
        head_passes_tests_results = list(
            tqdm(
                pool.imap(head_passes_tests, head_passes_tests_arguments),
                total=len(head_passes_tests_arguments),
            )
        )
    print("validate_repos: Finished Testing")

    print("validate_repos: Building Output")
    out = []
    valid_repos_mask = [i == TEST_STATE.Tests_passed for i in head_passes_tests_results]
    out = df[valid_repos_mask]
    print("validate_repos: Finished Building Output")

    print("validate_repos: Number of valid repos:", len(out), "out of", len(df))
    if len(out) == 0:
        raise Exception("No valid repos found")
    out.to_csv(args.output_path, index_label="idx")
    print("validate_repos: Done")
