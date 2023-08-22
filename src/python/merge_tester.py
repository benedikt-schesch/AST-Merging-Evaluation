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
from typing import Tuple
import random
import time
import psutil
import pandas as pd
from repo import Repository, MERGE_TOOL, TEST_STATE
from write_head_hashes import compute_num_cpus_used
from merge_tools_comparator import is_merge_sucess
from tqdm import tqdm

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore

TIMEOUT_TESTING_PARENT = 60 * 30  # 30 minutes, in seconds
TIMEOUT_TESTING_MERGE = 60 * 45  # 45 minutes, in seconds
N_RESTARTS = 3


def merge_tester(args: Tuple[str, pd.Series, Path]) -> pd.Series:
    """Tests the parents of a merge and in case of success, it tests the merge.
    Args:
        args (Tuple[str,pd.Series,Path]): A tuple containing the repository info and
                    the cache path.
    Returns:
        dict: The result of the test.
    """
    repo_slug, merge_data, cache_prefix = args
    while psutil.cpu_percent() > 90:
        print(
            "merge_tester: Waiting for CPU load to come down ",
            repo_slug,
            merge_data["left"],
            merge_data["right"],
        )
        time.sleep(60)
    print("merge_tester: Started ", repo_slug, merge_data["left"], merge_data["right"])

    merge_data["parents pass"] = False
    for branch in ["left", "right"]:
        repo = Repository(repo_slug, cache_prefix=cache_prefix)
        repo.checkout(merge_data[branch])
        tree_fingerprint = repo.compute_tree_fingerprint()
        assert tree_fingerprint == merge_data[f"{branch}_tree_fingerprint"]
        test_result = repo.test(TIMEOUT_TESTING_PARENT, N_RESTARTS)
        merge_data[f"{branch} test result"] = test_result.name
        if test_result != TEST_STATE.Tests_passed:
            return merge_data
        del repo

    merge_data["parents pass"] = True

    for merge_tool in MERGE_TOOL:
        if is_merge_sucess(merge_data[merge_tool.name]):
            repo = Repository(repo_slug, cache_prefix=cache_prefix)
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
                    repo_slug,
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


def main():  # pylint: disable=too-many-locals,too-many-statements
    """Main function"""
    print("merge_tester: Start")
    parser = argparse.ArgumentParser()
    parser.add_argument("--valid_repos_csv", type=Path)
    parser.add_argument("--merges_path", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--cache_dir", type=Path, default="cache/")
    args = parser.parse_args()
    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    repos = pd.read_csv(args.valid_repos_csv, index_col="idx")

    print("merge_tester: Constructing Inputs")
    merger_tester_arguments = []
    for _, repository_data in tqdm(repos.iterrows(), total=len(repos)):
        repo_slug = repository_data["repository"]
        merge_list_file = Path(
            os.path.join(args.merges_path, slug_repo_name(repo_slug) + ".csv")
        )
        output_file = Path(
            os.path.join(args.output_dir, slug_repo_name(repo_slug) + ".csv")
        )
        if not merge_list_file.exists():
            print(
                "merge_tester.py:",
                repo_slug,
                "does not have a list of merges. Missing file: ",
                merge_list_file,
            )
            continue

        if output_file.exists():
            print(
                "merge_tester.py: Skipping",
                repo_slug,
                "because it is already computed.",
            )
            continue
        try:
            merges = pd.read_csv(merge_list_file, header=0, index_col="idx")
        except pd.errors.EmptyDataError:
            print("merge_tester.py: Skipping", repo_slug, "because it is empty.")
            continue
        merges = merges[merges["two merge tools differ"]]
        merger_tester_arguments += [
            (repo_slug, merge_data, Path(args.cache_dir))
            for _, merge_data in merges.iterrows()
        ]

    # Shuffle input to reduce cache contention
    random.seed(42)
    random.shuffle(merger_tester_arguments)

    print("merge_tester: Finished Constructing Inputs")
    print("merge_tester: Number of tested merges:", len(merger_tester_arguments))

    print("merge_tester: Started Testing")
    with multiprocessing.Pool(processes=compute_num_cpus_used()) as pool:
        merge_tester_results = list(
            tqdm(
                pool.imap(merge_tester, merger_tester_arguments),
                total=len(merger_tester_arguments),
            )
        )
    print("merge_tester: Finished Testing")

    repo_result = {repo_slug: [] for repo_slug in repos["repository"]}
    print("merge_tester: Constructing Output")

    n_merges_parent_pass = 0
    for i in tqdm(range(len(merger_tester_arguments))):
        repo_slug = merger_tester_arguments[i][0]
        merge_results = merge_tester_results[i]
        if merge_results["parents pass"]:
            n_merges_parent_pass += 1
        repo_result[repo_slug].append(merge_results)

    n_total_merges = 0
    n_total_merges_parent_pass = 0
    for repo_slug in repo_result:
        output_file = Path(
            os.path.join(args.output_dir, slug_repo_name(repo_slug) + ".csv")
        )
        if output_file.exists():
            try:
                df = pd.read_csv(output_file, header=0)
            except pd.errors.EmptyDataError:
                print("merge_tester.py: Skipping", repo_slug, "because it is empty.")
                continue
            n_total_merges += len(df)
            n_total_merges_parent_pass += len(df[df["parents pass"]])
            continue
        df = pd.DataFrame(repo_result[repo_slug])
        df.sort_index(inplace=True)
        df.to_csv(output_file, index_label="idx")
        n_total_merges += len(df)
        n_total_merges_parent_pass += len(df[df["parents pass"]])

    print("merge_tester: Number of newly tested merges:", len(merger_tester_arguments))
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
    print("merge_tester: Done")


if __name__ == "__main__":
    main()
