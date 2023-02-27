#!/usr/bin/env python3
"""Perform and test merges with different merge tools."""

# usage: python3 merge_tester.py --repos_path <path_to_repo>
#                                         --merges_path <merges_path>
#                                         --output_path <output_path>
#
# This script takes a csv of repos and a csv of merges and performs the merges with
# the different merging tools. Each merge is then tested.
# An output file is generated with all the results for each merge.

import subprocess
import shutil
import os
import time
import multiprocessing
import argparse
from pathlib import Path
import platform

from validate_repos import repo_test
from tqdm import tqdm
import pandas as pd
import git


SCRATCH_DIR = "scratch/"
STORE_SCRATCH = False
WORKDIR = ".workdir/"
CACHE = "cache/merge_test_results/"
DELETE_WORKDIR = True
TIMEOUT_MERGE = 15 * 60  # 15 Minutes
TIMEOUT_TESTING = 45 * 60  # 45 Minutes


def test_merge(merging_method, repo_name, left, right, base):
    """Merges a repo and executes tests.
    Args:
        merging_method (str): Name of the merging method to use.
        repo_name (str): Name of the repo.
        left (str): Left parent hash of a merge.
        right (str): Right parent hash of a merge.
        base (str): Base parent hash of a merge.
    Returns:
        int: Test result of merge.
        float: Runtime to execute the merge.
    """
    try:
        repo_dir = "repos/" + repo_name
        process = multiprocessing.current_process()
        pid = str(process.pid)
        repo_dir_copy = WORKDIR + pid
        if os.path.isdir(repo_dir_copy):
            shutil.rmtree(repo_dir_copy)

        if platform.system() == "Linux":  # Linux
            command_timeout = "timeout"
        else:  # MacOS
            command_timeout = "gtimeout"

        shutil.copytree(repo_dir, repo_dir_copy + "/" + merging_method)
        repo = git.Repo(repo_dir_copy + "/" + merging_method)
        repo.remote().fetch()
        repo.git.checkout(left)
        repo.git.checkout("-b", "AOFKMAFNASFKJNRFQJXNFHJ1")
        repo.git.checkout(right)
        repo.git.checkout("-b", "AOFKMAFNASFKJNRFQJXNFHJ2")
        try:
            start = time.time()
            merge = subprocess.run(
                [
                    command_timeout,
                    str(TIMEOUT_MERGE) + "s",
                    "src/scripts/merge_tools/" + merging_method + ".sh",
                    repo_dir_copy + "/" + merging_method,
                    "AOFKMAFNASFKJNRFQJXNFHJ1",
                    "AOFKMAFNASFKJNRFQJXNFHJ2",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            runtime = time.time() - start
        except Exception:
            merge = 6
            runtime = -1
        try:
            if merge == 0:
                merge = (
                    repo_test(repo_dir_copy + "/" + merging_method, TIMEOUT_TESTING) + 2
                )
        except Exception:
            merge = 5
    except Exception:
        merge = -1
        runtime = -1
    if STORE_SCRATCH:
        dst_name = (
            SCRATCH_DIR
            + repo_name
            + "_"
            + left
            + "_"
            + right
            + "_"
            + base
            + "_"
            + merging_method
        )
        if os.path.isdir(dst_name):
            shutil.rmtree(dst_name)
        if os.path.isdir(repo_dir_copy + "/" + merging_method):
            shutil.copytree(repo_dir_copy + "/" + merging_method, dst_name)
    if os.path.isdir(repo_dir_copy):
        shutil.rmtree(repo_dir_copy)
    return merge, runtime


def test_merges(args):
    """Merges a repo with spork, intellimerge and git. Executes tests on
        all merges
    Args:
        repo_name (str): Name of the repo.
        left (str): Left parent hash of a merge.
        right (str): Right parent hash of a merge.
        base (str): Base parent hash of a merge.
        merge (str): Merge hash to be considered.
    Returns:
        int: Git merge test result.
        int: Spork merge test result.
        int: Intellimerge merge test result.
        float: Git runtime.
        float: Spork runtime.
        float: Intellimerge runtime.
    """
    repo_name, left, right, base, merge = args
    cache_file = (
        CACHE
        + repo_name.split("/")[1]
        + "_"
        + left
        + "_"
        + right
        + "_"
        + base
        + "_"
        + merge
        + ".csv"
    )

    if os.path.isfile(cache_file):
        result = pd.read_csv(cache_file, index_col=0)
        return (
            result.iloc[0][0],
            result.iloc[0][1],
            result.iloc[0][2],
            result.iloc[0][3],
            result.iloc[0][4],
            result.iloc[0][5],
        )

    out = pd.DataFrame([[-2, -2, -2, -2, -2, -2]])
    out.to_csv(cache_file)

    # Git Merge
    git_merge, git_runtime = test_merge("gitmerge", repo_name, left, right, base)

    # Spork Merge
    spork_merge, spork_runtime = test_merge("spork", repo_name, left, right, base)

    # IntelliMerge
    intelli_merge, intelli_runtime = test_merge(
        "intellimerge", repo_name, left, right, base
    )

    out = pd.DataFrame(
        [
            [
                git_merge,
                spork_merge,
                intelli_merge,
                git_runtime,
                spork_runtime,
                intelli_runtime,
            ]
        ]
    )
    out.to_csv(cache_file)

    return (
        git_merge,
        spork_merge,
        intelli_merge,
        git_runtime,
        spork_runtime,
        intelli_runtime,
    )


if __name__ == "__main__":
    print("merge_tester: Start")
    Path("repos").mkdir(parents=True, exist_ok=True)
    Path("cache").mkdir(parents=True, exist_ok=True)
    Path(CACHE).mkdir(parents=True, exist_ok=True)
    Path(WORKDIR).mkdir(parents=True, exist_ok=True)
    Path(SCRATCH_DIR).mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_path", type=str)
    parser.add_argument("--merges_path", type=str)
    parser.add_argument("--output_file", type=str)
    args = parser.parse_args()
    df = pd.read_csv(args.repos_path)

    print("merge_tester: Building Inputs")
    args_merges = []
    for idx, row in tqdm(df.iterrows(), total=len(df)):
        merge_list_file = args.merges_path + row["repository"].split("/")[1] + ".csv"
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(merge_list_file, index_col=0)

        for idx2, row2 in merges.iterrows():
            if row2["parent test"] != 0:
                continue
            args_merges.append(
                (
                    row["repository"],
                    row2["left"],
                    row2["right"],
                    row2["base"],
                    row2["merge"],
                )
            )

    print("merge_tester: Finished Building Inputs")

    print("merge_tester: Number of merges:", len(args_merges))
    print("merge_tester: Started Testing")
    with multiprocessing.Pool(processes=int(os.cpu_count() * 0.75)) as pool:
        r = list(
            tqdm(
                pool.imap(test_merges, args_merges), total=len(args_merges), miniters=1
            )
        )
    print("merge_tester: Finished Testing")
    print("merge_tester: Building Output")

    output = []
    for idx, row in tqdm(df.iterrows(), total=len(df)):
        merge_list_file = args.merges_path + row["repository"].split("/")[1] + ".csv"
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(merge_list_file, index_col=0)

        # Initialize new columns
        merges["repo_name"] = [row["repository"] for i in merges.iterrows()]
        merges["gitmerge"] = [-10 for i in merges.iterrows()]
        merges["spork"] = [-10 for i in merges.iterrows()]
        merges["intellimerge"] = [-10 for i in merges.iterrows()]
        merges["gitmerge runtime"] = [-10 for i in merges.iterrows()]
        merges["spork runtime"] = [-10 for i in merges.iterrows()]
        merges["intellimerge runtime"] = [-10 for i in merges.iterrows()]

        for idx2, row2 in merges.iterrows():
            (
                git_merge,
                spork_merge,
                intelli_merge,
                git_runtime,
                spork_runtime,
                intelli_runtime,
            ) = test_merges(
                (
                    row["repository"],
                    row2["left"],
                    row2["right"],
                    row2["base"],
                    row2["merge"],
                )
            )
            merges.loc[idx2, "gitmerge"] = git_merge
            merges.loc[idx2, "spork"] = spork_merge
            merges.loc[idx2, "intellimerge"] = intelli_merge
            merges.loc[idx2, "gitmerge runtime"] = git_runtime
            merges.loc[idx2, "spork runtime"] = spork_runtime
            merges.loc[idx2, "intellimerge runtime"] = intelli_runtime
        output.append(merges)
    output = pd.concat(output, ignore_index=True)
    output.to_csv(args.output_file)
    print("merge_tester: Finished Building Output")
    print("merge_tester: Done")
