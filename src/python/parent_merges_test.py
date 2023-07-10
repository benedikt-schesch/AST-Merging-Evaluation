#!/usr/bin/env python3
"""Tests the parents of a merge and subsamples merges from the merges with passing parents.

usage: python3 parent_merges_test.py --repos_csv <path_to_repos.csv>
                                     --merges_path <path_to_merges_directory>
                                     --output_dir <output_directory>
                                     --n_merges <max_number_of_merges>

This script takes a list of repositories and a path merges_path which contains a list of merges for 
each repository. The script verifies that the two parents of each merge has parents that pass tests.
It subsamples n_merges of merges that have passing parents for each repository.
The output is produced in <output_directory>.
"""

import shutil
import os
import itertools
import multiprocessing
from multiprocessing import Manager
import argparse
from pathlib import Path
from functools import partialmethod
from typing import Tuple, Union, Dict
import pandas as pd
import lockfile

from tqdm import tqdm
from validate_repos import commit_pass_test, del_rw, TEST_STATE

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore


WORKDIR = ".workdir/"
VALID_MERGE_COUNTERS = ".valid_merges/"
TIMEOUT_TESTING = 30 * 60  # 30 minutes


def num_valid_merges(repo_name: str) -> int:
    """Returns the number of merges that have passing parents for a repository.
    Args:
        repo_name (str): The name of the repository.
    Returns:
        int: The number of merges that have passing parents for the repository.
    """
    lock_file = os.path.join(VALID_MERGE_COUNTERS, repo_name + ".lock")
    valid_repo_count_file = os.path.join(VALID_MERGE_COUNTERS, repo_name)
    with lockfile.LockFile(lock_file, timeout=60):
        if os.path.isfile(valid_repo_count_file):
            with open(valid_repo_count_file, "r") as f:
                valid_merge_counter = int(f.read())
                return valid_merge_counter
        else:
            return 0


def increment_valid_merges(repo_name: str) -> None:
    """Increments the number of merges that have passing parents for a repository.
    Args:
        repo_name (str): The name of the repository.
    """
    lock_file = os.path.join(VALID_MERGE_COUNTERS, repo_name + ".lock")
    valid_repo_count_file = os.path.join(VALID_MERGE_COUNTERS, repo_name)
    with lockfile.LockFile(lock_file, timeout=60):
        if os.path.isfile(valid_repo_count_file):
            with open(valid_repo_count_file, "r") as f:
                valid_merge_counter = int(f.read())
            with open(valid_repo_count_file, "w") as f:
                f.write(str(valid_merge_counter + 1))
        else:
            with open(valid_repo_count_file, "w") as f:
                f.write("1")


def parent_pass_test(
    args: Tuple[str, str, str, str, int, str]
) -> Union[Tuple[TEST_STATE, TEST_STATE, TEST_STATE], None]:
    """Indicates whether the two parents of a merge pass tests. Only operates if no more than
        n_sampled other merges have passing parents.
    Args:
        args (Tuple[str, str, str, str, int]): A tuple containing
            the repository name, the left parent, the right parent, the merge commit,
            the maximum number of merges to sample, and the cache directory.
    Returns:
        Union[Tuple[TEST_STATE, TEST_STATE, TEST_STATE], None]: A tuple containing the test
            results for the left parent, the right parent, and the merge commit, or None if
            enough merges have been sampled.
    """
    repo_name, left, right, merge, n_sampled, cache_dir = args
    repo_file_name = repo_name.replace("/", "_")
    if num_valid_merges(repo_file_name) >= n_sampled:
        return None
    left_test = commit_pass_test(repo_name, left, "left_test", cache_dir)
    if left_test != TEST_STATE.Tests_passed:
        return left_test, TEST_STATE.Not_tested, TEST_STATE.Not_tested
    right_test = commit_pass_test(repo_name, right, "right_test", cache_dir)
    if right_test != TEST_STATE.Tests_passed:
        return left_test, right_test, TEST_STATE.Not_tested
    increment_valid_merges(repo_file_name)
    merge_test = commit_pass_test(
        repo_name, merge, f"merge of {left} and {right}", cache_dir
    )
    return left_test, right_test, merge_test


if __name__ == "__main__":
    print("parent_merges_test: Start")
    Path("repos").mkdir(parents=True, exist_ok=True)
    Path(WORKDIR).mkdir(parents=True, exist_ok=True)
    Path(VALID_MERGE_COUNTERS).mkdir(parents=True, exist_ok=True)

    pwd = os.getcwd()
    parser = argparse.ArgumentParser()
    parser.add_argument("--valid_repos_csv", type=str)
    parser.add_argument("--merges_path", type=str)
    parser.add_argument("--output_dir", type=str)
    parser.add_argument("--n_merges", type=int)
    parser.add_argument("--cache_dir", type=str, default="cache/test_result/")
    args = parser.parse_args()
    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.valid_repos_csv, index_col="idx")
    if os.path.isdir(args.output_dir):
        shutil.rmtree(args.output_dir, onerror=del_rw)
    os.mkdir(args.output_dir)

    multiprocessing_manager = Manager()

    print("parent_merges_test: Constructing Inputs")
    tested_merges = []
    for _, repository_data in tqdm(df.iterrows(), total=len(df)):
        merges_repo = []
        repo_name = repository_data["repository"]
        merge_list_file = os.path.join(
            args.merges_path, repo_name.split("/")[1] + ".csv"
        )
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(
            merge_list_file,
            names=["branch_name", "merge", "left", "right", "base"],
            header=0,
        )
        merges = merges.sample(frac=1, random_state=42)

        for _, merge_data in merges.iterrows():
            merges_repo.append(
                (
                    repo_name,
                    merge_data["left"],
                    merge_data["right"],
                    merge_data["merge"],
                    args.n_merges,
                    args.cache_dir,
                )
            )
        tested_merges.append(merges_repo)
    print("parent_merges_test: Finished Constructing Inputs")

    # `zip_longest` interleaves testing to reduce probability
    # that tests at the same hash happen in parallel.
    arguments = [
        val
        for l in itertools.zip_longest(*tested_merges)
        for val in l
        if val is not None
    ]
    assert len(arguments) == sum(len(l) for l in tested_merges)

    print("parent_merges_test: Number of tested commits:", len(arguments))
    print("parent_merges_test: Started Testing")
    cpu_count = os.cpu_count() or 1
    processes_used = cpu_count - 2 if cpu_count > 3 else cpu_count
    with multiprocessing.Pool(processes=processes_used) as pool:
        r = list(tqdm(pool.imap(parent_pass_test, arguments), total=len(arguments)))
    print("parent_merges_test: Finished Testing")

    # Delet all files in the valid merge counters directory
    for filename in os.listdir(VALID_MERGE_COUNTERS):
        file_path = os.path.join(VALID_MERGE_COUNTERS, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
        except Exception as e:
            print("Failed to delete {file_path}. Reason: {e}")

    print("parent_merges_test: Constructing Output")
    for _, repository_data in tqdm(df.iterrows(), total=len(df)):
        repo_name = repository_data["repository"]
        merge_list_file = args.merges_path + repo_name.split("/")[1] + ".csv"

        if not os.path.isfile(merge_list_file):
            raise Exception(
                repo_name
                + " does not have a list of merge. Missing file: "
                + merge_list_file
            )

        merges = pd.read_csv(
            merge_list_file,
            names=["branch_name", "merge", "left", "right", "base"],
            header=0,
        )
        merges = merges.sample(frac=1, random_state=42)
        merges["parent test"] = ["Failure" for i in merges.iterrows()]
        merges["merge test"] = ["Failure" for i in merges.iterrows()]

        result = []
        merges_counter = 0
        for merge_idx, merge_data in merges.iterrows():
            parents_result = parent_pass_test(
                (  # type: ignore
                    repo_name,
                    merge_data["left"],
                    merge_data["right"],
                    merge_data["merge"],
                    args.n_merges,
                    str(args.cache_dir),
                )
            )
            if parents_result is None:
                continue
            left_test, right_test, merge_test = parents_result
            merges.at[merge_idx, "merge test"] = merge_test.name
            if (
                left_test == TEST_STATE.Tests_passed
                and right_test == TEST_STATE.Tests_passed
            ):
                merges.at[merge_idx, "parent test"] = TEST_STATE.Tests_passed.name
                merges_counter += 1
                result.append(merges.loc[merge_idx])  # type: ignore
                print(
                    repo_name,
                    merge_data["merge"],
                    "passed",
                    "left:",
                    merge_data["left"],
                    "result:",
                    left_test,
                    "right:",
                    merge_data["right"],
                    "result:",
                    right_test,
                )
            else:
                print(
                    repo_name,
                    merge_data["merge"],
                    "failed",
                    "left:",
                    merge_data["left"],
                    "result:",
                    left_test,
                    "right:",
                    merge_data["right"],
                    "result:",
                    right_test,
                )
            if merges_counter >= args.n_merges:
                break
        result = pd.DataFrame(result)
        output_file = os.path.join(args.output_dir, repo_name.split("/")[1] + ".csv")
        result.to_csv(output_file, index_label="idx")
    print("parent_merges_test: Finished Constructing Output")
    print("parent_merges_test: Done")
