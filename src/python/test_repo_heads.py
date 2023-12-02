#!/usr/bin/env python3
"""Tests the HEAD commits of multiple repos and considers them as valid if the test passes.

usage: python3 test_repo_heads.py --repos_csv_with_hashes <repos_csv_with_hashes.csv>
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
import shutil
from functools import partialmethod
from typing import Tuple
from repo import Repository, TEST_STATE
from variables import TIMEOUT_TESTING_PARENT
from tqdm import tqdm
import pandas as pd
from cache_utils import set_in_cache, lookup_in_cache


if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore


def num_processes() -> int:
    """Compute the number of CPUs to be used
    Returns:
        int: the number of CPUs to be used.
    """
    cpu_count = os.cpu_count() or 1
    processes_used = int(0.7 * cpu_count) if cpu_count > 3 else cpu_count
    return processes_used


def head_passes_tests(args: Tuple[pd.Series, Path]) -> pd.Series:
    """Runs tests on the head of the main branch.
    Args:
        args (Tuple[pd.Series,Path]): A tuple containing the repository info and the cache path.
    Returns:
        TEST_STATE: The result of the test.
    """
    repo_info, cache = args
    repo_slug = repo_info["repository"]
    if "/" not in repo_slug:
         repo_info["head test result"] = "Wrong format"
         return repo_info
    cache_key = repo_slug
    merge_cache_directory = cache / "repos_head_info"
    cache_data = lookup_in_cache(cache_key, repo_slug, merge_cache_directory, True)

    # Check if data is in cache
    if cache_data is not None and isinstance(cache_data, dict):
        for key, value in cache_data.items():
            repo_info[key] = value
        if cache_data["head test result"] == TEST_STATE.Tests_passed.name:
            # Make sure the repo is cloned
            repo = Repository(
                repo_slug,
                cache_directory=cache,
                workdir_id=repo_slug + "/head-" + repo_info["repository"],
            )
        return repo_info

    print("test_repo_heads:", repo_slug, ": head_passes_tests : started")
    cache_data = {}

    # Load repo
    try:
        repo = Repository(
            repo_slug,
            cache_directory=cache,
            workdir_id=repo_slug + "/head-" + repo_info["repository"],
        )
        if "head hash" in repo_info:
            cache_data["head hash"] = repo_info["head hash"]
        else:
            cache_data["head hash"] = repo.get_head_hash()
        cache_data["tree fingerprint"] = repo.compute_tree_fingerprint()
    except Exception as e:
        print("test_repo_heads:", repo_slug, ": exception head_passes_tests :", e)
        cache_data["head test result"] = TEST_STATE.Git_checkout_failed.name
        cache_data["explanation"] = str(e)
        set_in_cache(cache_key, cache_data, repo_slug, merge_cache_directory, True)
        for key, value in cache_data.items():
            repo_info[key] = value
        return repo_info

    # Test repo
    test_state, _, _ = repo.checkout_and_test(
        cache_data["head hash"], timeout=TIMEOUT_TESTING_PARENT, n_tests=3
    )
    cache_data["head test result"] = test_state.name
    set_in_cache(cache_key, cache_data, repo_slug, merge_cache_directory, True)

    if test_state != TEST_STATE.Tests_passed:
        shutil.rmtree(repo.path, ignore_errors=True)

    for key, value in cache_data.items():
        repo_info[key] = value

    print("test_repo_heads:", repo_slug, ": head_passes_tests : returning", test_state)
    return repo_info


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_csv_with_hashes", type=Path)
    parser.add_argument("--output_path", type=Path)
    parser.add_argument("--cache_dir", type=Path, default="cache/")
    args = parser.parse_args()

    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.repos_csv_with_hashes, index_col="idx")

    print("test_repo_heads: Started Testing")
    head_passes_tests_arguments = [(v, args.cache_dir) for _, v in df.iterrows()]
    with multiprocessing.Pool(processes=num_processes()) as pool:
        head_passes_tests_results = list(
            tqdm(
                pool.imap(head_passes_tests, head_passes_tests_arguments),
                total=len(head_passes_tests_arguments),
            )
        )
    print("test_repo_heads: Finished Testing")

    print("test_repo_heads: Started Building Output")
    df = pd.DataFrame(head_passes_tests_results)
    filtered_df = df[df["head test result"] == TEST_STATE.Tests_passed.name]
    print("test_repo_heads: Finished Building Output")

    print(
        "test_repo_heads: Number of repos whose head passes tests:",
        len(filtered_df),
        "out of",
        len(df),
    )
    if len(filtered_df) == 0:
        raise Exception("No repos found whose head passes tests")
    filtered_df.to_csv(args.output_path, index_label="idx")
    df.to_csv(
        args.output_path.parent / "all_repos_head_test_results.csv", index_label="idx"
    )
    print("test_repo_heads: Done")
