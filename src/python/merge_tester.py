#!/usr/bin/env python3
"""Test the merges and check if the parents pass tests.
usage: python3 merge_tester.py --valid_repos_csv <path_to_valid_repos.csv>
                                --merges_path <path_to_merges>
                                --output_dir <output_dir>
                                --cache_dir <cache_dir>
This script tests the merges and checks if the parents pass tests. 
The output is written in output_dir. For each repository a csv output file
is created that contains information including testing information regarding
each merge.
"""

import os
import multiprocessing
import argparse
from pathlib import Path
from functools import partialmethod
from typing import Tuple, Union
import random
import pandas as pd
from repo import Repository, MERGE_TOOL, MERGE_STATE, TEST_STATE
from valid_merge_counters import (
    read_valid_merges_counter,
    increment_valid_merges,
    delete_valid_merges_counters,
)
from merge_filter import is_merge_sucess
from tqdm import tqdm

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore

TIMEOUT_TESTING_PARENT = 60 * 30  # 30 minutes, in seconds
TIMEOUT_TESTING_MERGE = 60 * 45  # 45 minutes, in seconds
N_RESTARTS = 3


def merge_tester(args: Tuple[str, pd.Series, Path, int]) -> Union[pd.Series, None]:
    """Tests the parents of a merge and in case of success, it tests the merge.
    Args:
        args (Tuple[str,pd.Series,Path,int]): A tuple containing the repository info and
                    the cache path and the number of sampled merges.
    Returns:
        dict: The result of the test.
    """
    repo_name, merge_data, cache_prefix, n_samples = args
    print("merge_tester: Started ", repo_name, merge_data["left"], merge_data["right"])

    n_valid_merges = read_valid_merges_counter(repo_name)
    if n_valid_merges > n_samples:
        return None

    merge_data["parents pass"] = False
    for branch in ["left", "right"]:
        repo = Repository(repo_name, cache_prefix=cache_prefix)
        repo.checkout(merge_data[branch])
        tree_fingerprint = repo.compute_tree_fingerprint()
        assert tree_fingerprint == merge_data[f"{branch}_tree_fingerprint"]
        test_result = repo.test(TIMEOUT_TESTING_PARENT, N_RESTARTS)
        merge_data[f"{branch} test result"] = test_result.name
        n_valid_merges = read_valid_merges_counter(repo_name)
        if n_valid_merges > n_samples:
            return None
        if test_result != TEST_STATE.Tests_passed:
            return merge_data
        del repo

    increment_valid_merges(repo_name)
    merge_data["parents pass"] = True

    for merge_tool in MERGE_TOOL:
        if is_merge_sucess(merge_data[merge_tool.name]):
            repo = Repository(repo_name, cache_prefix=cache_prefix)
            (
                result,
                merge_fingerprint,
                left_fingerprint,
                right_fingerprint,
                _,
            ) = repo.merge_and_test_cached(
                tool=merge_tool,
                left_commit=merge_data["left"],
                right_commit=merge_data["right"],
                timeout=TIMEOUT_TESTING_MERGE,
                n_restarts=N_RESTARTS,
            )
            assert left_fingerprint == merge_data["left_tree_fingerprint"]
            assert right_fingerprint == merge_data["right_tree_fingerprint"]
            if merge_fingerprint != merge_data[merge_tool.name + "_merge_fingerprint"]:
                raise Exception(
                    "merge_tester: Merge fingerprint mismatch",
                    repo_name,
                    merge_data["left"],
                    merge_data["right"],
                    merge_tool.name,
                    result,
                    merge_fingerprint,
                    merge_data[merge_tool.name + "_merge_fingerprint"],
                )
            merge_data[merge_tool.name] = result.name
            del repo
        assert merge_tool.name in merge_data
    return merge_data


def main():
    print("merge_tester: Start")
    parser = argparse.ArgumentParser()
    parser.add_argument("--valid_repos_csv", type=Path)
    parser.add_argument("--merges_path", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--n_merges", type=int, default=2)
    parser.add_argument("--cache_dir", type=Path, default="cache/")
    args = parser.parse_args()
    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    repos = pd.read_csv(args.valid_repos_csv, index_col="idx")
    delete_valid_merges_counters()

    print("merge_tester: Constructing Inputs")
    arguments = []
    for _, repository_data in tqdm(repos.iterrows(), total=len(repos)):
        merges_repo = []
        repo_name = repository_data["repository"]
        merge_list_file = Path(
            os.path.join(args.merges_path, repo_name.split("/")[1] + ".csv")
        )
        output_file = Path(
            os.path.join(args.output_dir, repo_name.split("/")[1] + ".csv")
        )
        if not merge_list_file.exists():
            print(
                "merge_tester.py:",
                repo_name,
                "does not have a list of merges. Missing file: ",
                merge_list_file,
            )
            continue

        if output_file.exists():
            print(
                "merge_tester.py: Skipping",
                repo_name,
                "because it is already computed.",
            )
            continue
        try:
            merges = pd.read_csv(merge_list_file, header=0, index_col="idx")
        except pd.errors.EmptyDataError:
            print("merge_tester.py: Skipping", repo_name, "because it is empty.")
            continue
        merges = merges[merges["analyze"]]
        arguments += [
            (repo_name, merge_data, Path(args.cache_dir), args.n_merges)
            for _, merge_data in merges.iterrows()
        ]

    # Shuffle input to reduce cache contention
    random.seed(42)
    random.shuffle(arguments)

    print("merge_tester: Finished Constructing Inputs")
    print("merge_tester: Number of tested merges:", len(arguments))

    print("merge_tester: Started Testing")
    cpu_count = os.cpu_count() or 1
    processes_used = int(cpu_count * 0.7) if cpu_count > 3 else cpu_count
    with multiprocessing.Pool(processes=processes_used) as pool:
        result = list(tqdm(pool.imap(merge_tester, arguments), total=len(arguments)))
    print("merge_tester: Finished Testing")

    results = {repo_name: [] for repo_name in repos["repository"]}
    print("merge_tester: Constructing Output")

    n_merges_parent_pass = 0
    for i in tqdm(range(len(arguments))):
        repo_name = arguments[i][0]
        merge_results = result[i]
        if merge_results is None:
            continue
        if merge_results["parents pass"]:
            n_merges_parent_pass += 1
        results[repo_name].append(merge_results)

    n_total_merges = 0
    n_total_merges_parent_pass = 0
    for repo_name in results:
        output_file = Path(
            os.path.join(args.output_dir, repo_name.split("/")[1] + ".csv")
        )
        if output_file.exists():
            try:
                df = pd.read_csv(output_file, header=0)
            except pd.errors.EmptyDataError:
                print("merge_tester.py: Skipping", repo_name, "because it is empty.")
                continue
            n_total_merges += len(df)
            n_total_merges_parent_pass += len(df[df["parents pass"]])
            continue
        df = pd.DataFrame(results[repo_name])
        df.sort_index(inplace=True)
        df.to_csv(output_file, index_label="idx")
        n_total_merges += len(df)
        n_total_merges_parent_pass += len(df[df["parents pass"]])

    print("merge_tester: Number of newly tested merges:", len(arguments))
    print(
        "merge_tester: Number of newly tested merges with parents pass:",
        n_merges_parent_pass,
    )
    print("merge_tester: Total number of tested merges:", n_total_merges)
    print(
        "merge_tester: Total number of merges with parents pass:",
        n_total_merges_parent_pass,
    )
    print("merge_tester: Finished Constructing Output")
    delete_valid_merges_counters()
    print("merge_tester: Done")


if __name__ == "__main__":
    main()
