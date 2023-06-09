#!/usr/bin/env python3
"""Perform and test merges with different merge tools.

usage: python3 merge_tester.py --repos_csv <path_to_repos.csv>
                               --merges_path <path_to_merges_directory>
                               --output_path <output_path>

This script takes a csv of repos and a csv of merges and performs the merges with
the different merging tools. Each merge is then tested.
An output file is generated with all the results for each merge.
"""

import signal
import subprocess
import shutil
import os
import time
import multiprocessing
import argparse
import traceback
from pathlib import Path

from validate_repos import repo_test
from tqdm import tqdm  # shows a progress meter as a loop runs
import pandas as pd
import git.repo


SCRATCH_DIR = "scratch/"
# If true, the merged repository will be stored.
# Otherwise, it is deleted after its tests are run.
STORE_SCRATCH = False
# If true, the working directories will be deleted.
# Otherwise, it is deleted after its tests are run.
DELETE_WORKDIR = True
WORKDIR = ".workdir/"
CACHE = "cache/merge_test_results/"
TIMEOUT_MERGE = 15 * 60  # 15 Minutes
TIMEOUT_TESTING = 45 * 60  # 45 Minutes
UNIQUE_COMMIT_NAME = "AOFKMAFNASFKJNRFQJXNFHJ"
MERGE_TOOLS = ["gitmerge", "spork", "intellimerge"]


def test_merge(
    merging_method, repo_name, left, right, base
):  # pylint: disable=too-many-locals, disable=too-many-statements
    """Merges a repo and executes its tests.
    Args:
        merging_method (str): Name of the merging method to use.
        repo_name (str): Name of the repo.
        left (str): Left parent hash of a merge.
        right (str): Right parent hash of a merge.
        base (str): Base parent hash of a merge.
    Returns:
        int: Test result of merge.  0 means success, non-zero means failure.
        float: Runtime to execute the merge.
    """
    # Variable `merge` is returned by this routine.
    repo_dir = "repos/" + repo_name
    process = multiprocessing.current_process()
    pid = str(process.pid)
    repo_dir_copy = WORKDIR + pid + "/repo"
    try:
        if os.path.isdir(repo_dir_copy):
            shutil.rmtree(repo_dir_copy)

        shutil.copytree(repo_dir, repo_dir_copy + "/" + merging_method)
        repo = git.repo.Repo(repo_dir_copy + "/" + merging_method)
        repo.remote().fetch()
        repo.submodule_update()
        repo.git.checkout(left, force=True)
        repo.git.checkout("-b", UNIQUE_COMMIT_NAME + "1", force=True)
        repo.git.checkout(right, force=True)
        repo.git.checkout("-b", UNIQUE_COMMIT_NAME + "2", force=True)
        start = time.time()
        try:
            p = subprocess.run(  # pylint: disable=consider-using-with
                [
                    "src/scripts/merge_tools/" + merging_method + ".sh",
                    repo_dir_copy + "/" + merging_method,
                    UNIQUE_COMMIT_NAME + "1",
                    UNIQUE_COMMIT_NAME + "2",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=TIMEOUT_MERGE,
            )
            merge = p.returncode
            runtime = time.time() - start
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)  # type: ignore
            runtime = time.time() - start
            merge = 124  # Timeout
        except Exception as e:
            merge = 6
            runtime = -1
            print(
                repo_name,
                merging_method,
                base,
                "Exception during merge. Exception:\n",
                e,
            )
        try:
            if merge == 0:
                merge, explanation = repo_test(
                    repo_dir_copy + "/" + merging_method, TIMEOUT_TESTING
                )
                print(
                    repo_name + " " + merging_method + " testing with return code:",
                    merge,
                )
                merge += 2
        except Exception as e:
            merge = 5
            print(
                repo_name,
                merging_method,
                base,
                "Exception during testing of the merge. Exception:\n",
                e,
            )
    except Exception as e:
        merge = -1
        runtime = -1
        print(
            repo_name,
            merging_method,
            base,
            "General exception during the handling of the repository. Exception:\n",
            e,
        )
        print(traceback.format_exc())
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
        repo_name (str): Name of the repo, in "ORGANIZATION/REPO" format.
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
        return result.iloc[0, :].values

    out = pd.DataFrame([[-2, -2, -2, -2, -2, -2]])
    out.to_csv(cache_file)

    merge_results = []
    merge_runtimes = []
    for merge_tool in MERGE_TOOLS:
        merge_result, merge_runtime = test_merge(
            merge_tool, repo_name, left, right, base
        )
        merge_results.append(merge_result)
        merge_runtimes.append(merge_runtime)

    out = pd.DataFrame([merge_results + merge_runtimes])
    out.to_csv(cache_file)

    return out.iloc[0, :].values


if __name__ == "__main__":
    print("merge_tester: Start")
    Path("repos").mkdir(parents=True, exist_ok=True)
    Path("cache").mkdir(parents=True, exist_ok=True)
    Path(CACHE).mkdir(parents=True, exist_ok=True)
    Path(WORKDIR).mkdir(parents=True, exist_ok=True)
    Path(SCRATCH_DIR).mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_csv", type=str)
    parser.add_argument("--merges_path", type=str)
    parser.add_argument("--output_file", type=str)
    args = parser.parse_args()
    df = pd.read_csv(args.repos_csv)

    print("merge_tester: Building Inputs")
    args_merges = []
    for _, row in tqdm(df.iterrows(), total=len(df)):
        merge_list_file = args.merges_path + row["repository"].split("/")[1] + ".csv"
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(merge_list_file, index_col=0)

        for _, row2 in merges.iterrows():
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
    cpu_count = os.cpu_count() or 1
    processes_used = cpu_count - 2 if cpu_count > 3 else cpu_count
    with multiprocessing.Pool(processes=processes_used) as pool:
        r = list(
            tqdm(
                pool.imap(test_merges, args_merges), total=len(args_merges), miniters=1
            )
        )
    print("merge_tester: Finished Testing")
    print("merge_tester: Building Output")

    output = []
    for _, row in tqdm(df.iterrows(), total=len(df)):
        merge_list_file = args.merges_path + row["repository"].split("/")[1] + ".csv"
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(merge_list_file, index_col=0)

        # Initialize new columns
        merges["repo_name"] = [row["repository"] for i in merges.iterrows()]
        for merge_tool in MERGE_TOOLS:
            merges[merge_tool] = [-10 for i in merges.iterrows()]
        for merge_tool in MERGE_TOOLS:
            merges[merge_tool + " runtime"] = [-10 for i in merges.iterrows()]

        for merge_idx, row2 in merges.iterrows():
            results = test_merges(
                (
                    row["repository"],
                    row2["left"],
                    row2["right"],
                    row2["base"],
                    row2["merge"],
                )
            )
            for merge_tool_idx, merge_tool in enumerate(MERGE_TOOLS):
                merges.at[merge_idx, merge_tool] = results[merge_tool_idx]
                merges.at[merge_idx, merge_tool + " runtime"] = results[
                    len(MERGE_TOOLS) + merge_tool_idx
                ]
        output.append(merges)
    output = pd.concat(output, ignore_index=True)
    output.to_csv(args.output_file)
    print("merge_tester: Finished Building Output")
    print("merge_tester: Number of analyzed merges ", len(output))
    print("merge_tester: Done")
