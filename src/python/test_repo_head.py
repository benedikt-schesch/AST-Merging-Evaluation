#!/usr/bin/env python3
"""Tests the HEAD of a repo and validates it if the test passes.

usage: python3 test_repo_head.py --repos_csv_with_hashes <repos_csv_with_hashes.csv>
                                 --output_path <repos_head_passes.csv>
                                 --cache_dir <cache_dir>

Input: a csv of repos.  It must contain a header, one of whose columns is "repository".
That column contains "ORGANIZATION/REPO" for a GitHub repository. The csv must also
contain a column "head hash" which contains a commit hash that will be tested. 
Cache_dir is the directory where the cache will be stored.
Output: the rows of the input for which the commit at head hash passes tests.
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
from write_head_hashes import compute_num_process_used, clone_repo

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore


TIMEOUT_TESTING = 60 * 30  # 30 minutes, in seconds.


def head_passes_tests(args: Tuple[pd.Series, Path]) -> TEST_STATE:
    """Runs tests on the head of the main branch.
    Args:
        args (Tuple[pd.Series,Path]): A tuple containing the repository info and the cache path.
    Returns:
        TEST_STATE: The result of the test.
    """
    repo_info, cache = args
    repo_slug = repo_info["repository"]
    print("test_repo_head:", repo_slug, ": head_passes_tests : started")

    repo = Repository(repo_slug, cache_prefix=cache)
    test_state = repo.checkout_and_test(
        repo_info["head hash"], timeout=TIMEOUT_TESTING, n_tests=3
    )
    print("test_repo_head:", repo_slug, ": head_passes_tests : returning", test_state)
    return test_state


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_csv_with_hashes", type=Path)
    parser.add_argument("--output_path", type=Path)
    parser.add_argument("--cache_dir", type=Path, default="cache/")
    args = parser.parse_args()

    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.repos_csv_with_hashes, index_col="idx")

    print("test_repo_head: Started cloning repos")
    with multiprocessing.Pool(processes=compute_num_process_used()) as pool:
        results = [
            pool.apply_async(clone_repo, args=(row["repository"],))
            for _, row in df.iterrows()
        ]
        for result in tqdm(results, total=len(results)):
            try:
                return_value = result.get(10 * 60)
            except Exception as e:
                print("Couldn't clone repo", e)
    print("test_repo_head: Finished cloning repos")

    if os.path.exists(args.output_path):
        print("test_repo_head: Output file already exists. Exiting.")
        sys.exit(0)

    print("test_repo_head: Started Testing")
    head_passes_tests_arguments = [(v, args.cache_dir) for _, v in df.iterrows()]
    with multiprocessing.Pool(processes=compute_num_process_used()) as pool:
        head_passes_tests_results = list(
            tqdm(
                pool.imap(head_passes_tests, head_passes_tests_arguments),
                total=len(head_passes_tests_arguments),
            )
        )
    print("test_repo_head: Finished Testing")

    print("test_repo_head: Started Building Output")
    out = []
    repos_head_passes_mask = [
        i == TEST_STATE.Tests_passed for i in head_passes_tests_results
    ]
    out = df[repos_head_passes_mask]
    print("test_repo_head: Finished Building Output")

    print(
        "test_repo_head: Number of repos whose head passes tests:",
        len(out),
        "out of",
        len(df),
    )
    if len(out) == 0:
        raise Exception("No repos found whose head passes tests")
    out.to_csv(args.output_path, index_label="idx")
    print("test_repo_head: Done")
