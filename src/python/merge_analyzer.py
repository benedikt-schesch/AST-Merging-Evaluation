#!/usr/bin/env python3
""" Analyze the merges i.e. check if the parents pass tests and statistics between merges.
usage: python3 merge_analyzer.py --repos_head_passes_csv <path_to_repos_head_passes.csv>
                                --merges_path <path_to_merges>
                                --output_dir <output_dir>
                                --cache_dir <cache_dir>
This script analyzes the merges i.e. it checks if the parents pass tests and it
computes statistics between merges.
The output is written in output_dir and consists of the same merges as the input
but with the test results and statistics.
"""

import os
import multiprocessing
import subprocess
import argparse
from pathlib import Path
from functools import partialmethod
from typing import Tuple
import random
import numpy as np
import pandas as pd
from repo import Repository, MERGE_TOOL, TEST_STATE, MERGE_STATE
from tqdm import tqdm
from cache_utils import set_in_cache, lookup_in_cache, slug_repo_name
from write_head_hashes import num_processes
from variables import TIMEOUT_MERGING, TIMEOUT_TESTING_PARENT, N_TESTS

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore


def is_test_passed(test_state: str) -> bool:
    """Returns true if the test state indicates passed tests."""
    return test_state == TEST_STATE.Tests_passed.name


def merge_analyzer(  # pylint: disable=too-many-locals,too-many-statements
    args: Tuple[str, pd.Series, Path]
) -> pd.Series:
    """
    Merges two branches and returns the result.
    Args:
        args (Tuple[str,pd.Series,Path]): A tuple containing the repo slug,
                the merge data (which is side-effected), and the cache path.
    Returns:
        dict: A dictionary containing the merge result.
    """
    repo_slug, merge_data, cache_directory = args

    cache_key = merge_data["left"] + "_" + merge_data["right"]
    merge_cache_directory = cache_directory / "merge_analysis"

    cache_data = lookup_in_cache(cache_key, repo_slug, merge_cache_directory, True)
    if cache_data is not None and isinstance(cache_data, dict):
        for key, value in cache_data.items():
            merge_data[key] = value
        return merge_data
    print("merge_analyzer: Analyzing", repo_slug, cache_key)

    cache_data = {}
    left_sha = merge_data["left"]
    right_sha = merge_data["right"]
    repo_left = Repository(
        repo_slug,
        cache_directory=cache_directory,
        workdir_id=repo_slug + "/left-" + left_sha + "-" + right_sha,
    )
    repo_right = Repository(
        repo_slug,
        cache_directory=cache_directory,
        workdir_id=repo_slug + "/right-" + left_sha + "-" + right_sha,
    )
    left_success, _ = repo_left.checkout(left_sha)
    right_success, _ = repo_right.checkout(right_sha)

    # Compute diff size in lines between left and right
    assert repo_left.repo_path.exists()
    assert repo_right.repo_path.exists()
    command = (
        f"diff -r {repo_left.repo_path} {repo_right.repo_path} | grep -a '^>' | wc -l"
    )
    process = process = subprocess.run(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    diff_size = int(process.stdout.strip())
    cache_data["diff_size"] = diff_size

    # List all files that are different between left and right
    process = subprocess.run(
        ["diff", "-r", "--brief", str(repo_left.repo_path), str(repo_right.repo_path)],
        stdout=subprocess.PIPE,
        text=True,
    )

    diff_files = process.stdout.split("\n") if process.stdout else []
    diff_files = [line.split()[-1] for line in diff_files if line]

    # Check if diff contains a java file
    contains_java_file = any(file.endswith(".java") for file in diff_files)
    cache_data["diff_contains_java_file"] = contains_java_file

    # Test left parent
    if not left_success:
        # This should never happen.  Search output for "Git_checkout_failed"
        cache_data["left parent test result"] = TEST_STATE.Git_checkout_failed.name
        cache_data["left_tree_fingerprint"] = None
        cache_data["left parent test coverage"] = None
        cache_data["parents pass"] = False
    else:
        cache_data["left_tree_fingerprint"] = repo_left.compute_tree_fingerprint()
        result, test_coverage = repo_left.test(TIMEOUT_TESTING_PARENT, N_TESTS)
        cache_data["left parent test result"] = result.name
        cache_data["left parent test coverage"] = test_coverage
        cache_data["parents pass"] = is_test_passed(
            cache_data["left parent test result"]
        )

    # Test right parent
    if not right_success:
        # This should never happen.  Search output for "Git_checkout_failed"
        cache_data["right parent test result"] = TEST_STATE.Git_checkout_failed.name
        cache_data["right_tree_fingerprint"] = None
        cache_data["right parent test coverage"] = None
        cache_data["parents pass"] = False
    else:
        cache_data["right_tree_fingerprint"] = repo_right.compute_tree_fingerprint()
        result, test_coverage = repo_right.test(TIMEOUT_TESTING_PARENT, N_TESTS)
        cache_data["right parent test result"] = result.name
        cache_data["right parent test coverage"] = test_coverage
        cache_data["parents pass"] = cache_data["parents pass"] and is_test_passed(
            cache_data["right parent test result"]
        )

    cache_data["test merge"] = (
        cache_data["parents pass"]
        and cache_data["diff_contains_java_file"]
        and cache_data["left parent test coverage"] is not None
        and cache_data["right parent test coverage"] is not None
    )

    set_in_cache(cache_key, cache_data, repo_slug, merge_cache_directory)

    print("merge_analyzer: Analyzed", repo_slug, cache_key)

    for key, value in cache_data.items():
        merge_data[key] = value

    return merge_data


def build_merge_analyzer_arguments(args: argparse.Namespace, repo_slug: str):
    """
    Creates the arguments for the merger function.
    Args:
        args (argparse.Namespace): The arguments to the script.
        repo_slug (str): The repository slug.
    Returns:
        list: A list of arguments for the merger function.
    """
    merge_list_file = Path(
        os.path.join(args.merges_path, slug_repo_name(repo_slug) + ".csv")
    )
    output_file = Path(
        os.path.join(args.output_dir, slug_repo_name(repo_slug) + ".csv")
    )
    if not merge_list_file.exists():
        print(
            "merge_analyzer:",
            repo_slug,
            "does not have a list of merges. Missing file: ",
            merge_list_file,
        )
        return []

    if output_file.exists():
        print(
            "merge_analyzer: Skipping",
            repo_slug,
            "because it is already computed.",
        )
        return []

    merges = pd.read_csv(
        merge_list_file,
        names=["idx", "branch_name", "merge", "left", "right", "notes"],
        dtype={
            "idx": int,
            "branch_name": str,
            "merge": str,
            "left": str,
            "right": str,
            "notes": str,
        },
        header=0,
        index_col="idx",
    )
    merges["notes"].replace(np.nan, "", inplace=True)

    arguments = [
        (repo_slug, merge_data, Path(args.cache_dir))
        for _, merge_data in merges.iterrows()
    ]
    return arguments


if __name__ == "__main__":
    print("merge_analyzer: Start")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_head_passes_csv", type=Path)
    parser.add_argument("--merges_path", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--cache_dir", type=Path, default="cache/merges/")
    args = parser.parse_args()
    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    repos = pd.read_csv(args.repos_head_passes_csv, index_col="idx")

    print("merge_analyzer: Constructing Inputs")
    merger_arguments = []
    for _, repository_data in tqdm(repos.iterrows(), total=len(repos)):
        repo_slug = repository_data["repository"]
        merger_arguments += build_merge_analyzer_arguments(args, repo_slug)

    # Shuffle input to reduce cache contention
    random.seed(42)
    random.shuffle(merger_arguments)

    print("merge_analyzer: Finished Constructing Inputs")
    # New merges are merges whose analysis does not appear in the output folder.
    print("merge_analyzer: Number of new merges:", len(merger_arguments))

    print("merge_analyzer: Started Merging")
    with multiprocessing.Pool(processes=num_processes()) as pool:
        merger_results = list(
            tqdm(
                pool.imap(merge_analyzer, merger_arguments), total=len(merger_arguments)
            )
        )
    print("merge_analyzer: Finished Merging")

    repo_result = {repo_slug: [] for repo_slug in repos["repository"]}
    print("merge_analyzer: Constructing Output")
    n_new_analyzed = 0
    n_new_to_test = 0
    for i in tqdm(range(len(merger_arguments))):
        repo_slug = merger_arguments[i][0]
        results_data = merger_results[i]

        repo_result[repo_slug].append(merger_results[i])
        n_new_analyzed += 1
        if results_data["test merge"]:
            n_new_to_test += 1

    n_total_analyzed = 0
    n_total_to_test = 0
    for repo_slug in repo_result:
        output_file = Path(
            os.path.join(args.output_dir, slug_repo_name(repo_slug) + ".csv")
        )
        if output_file.exists():
            try:
                df = pd.read_csv(output_file, header=0)
                if len(df) == 0:
                    continue
                n_total_analyzed += len(df)
                n_total_to_test += len(df[df["test merge"]])
            except pd.errors.EmptyDataError:
                print(
                    "merge_analyzer: Skipping",
                    repo_slug,
                    "because it does not contain any merges.",
                )
            continue
        df = pd.DataFrame(repo_result[repo_slug])
        if len(df) == 0:
            continue
        df.sort_index(inplace=True)
        df.to_csv(output_file, index_label="idx")
        n_total_analyzed += len(df)
        n_total_to_test += len(df[df["test merge"]])

    print(
        "merge_analyzer: Number of merge tool outputs that have been newly compared:",
        n_new_analyzed,
    )
    print(
        "merge_analyzer: Number of merge tool outputs that have been newly compared",
        "and are to test:",
        n_new_to_test,
    )
    print(
        "merge_analyzer: Total number of merge tool outputs that have been compared:",
        n_total_analyzed,
    )
    print(
        "merge_analyzer: Total number of merge tool outputs that have been compared",
        "and are to test:",
        n_total_to_test,
    )
    print("merge_analyzer: Finished Constructing Output")
    print("merge_analyzer: Done")
