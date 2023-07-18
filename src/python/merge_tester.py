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
import glob
import time
import multiprocessing
import argparse
from pathlib import Path
from functools import partialmethod
from enum import Enum
from typing import Tuple
import uuid

from tqdm import tqdm  # shows a progress meter as a loop runs
import pandas as pd
import git.repo
from validate_repos import repo_test, del_rw, TEST_STATE

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore


SCRATCH_DIR = "scratch/"
# If true, the merged repository under SCRATCH_DIR will be retained.
# Otherwise, it is deleted after its tests are run.
STORE_SCRATCH = False
WORKDIR = ".workdir/"
# If true, the working directories in WORKDIR will be retained.
# Otherwise, it is deleted after its tests are run.
STORE_WORKDIR = False
TIMEOUT_MERGE = 15 * 60  # 15 Minutes
TIMEOUT_TESTING = 45 * 60  # 45 Minutes
BRANCH_BASE_NAME = "___MERGE_TESTER"
LEFT_BRANCH_NAME = BRANCH_BASE_NAME + "_LEFT"
RIGHT_BRANCH_NAME = BRANCH_BASE_NAME + "_RIGHT"
MERGE_TOOLS = sorted(
    [
        os.path.basename(file)[:-3]
        for file in glob.glob("src/scripts/merge_tools/*")
        if file[-3:] == ".sh"
    ]
)

MERGE_STATES = Enum(
    "MERGE_STATES",
    [
        "Merge_failed",
        "Merge_exception",
        "Merge_timedout",
        "Merge_success",
        "Tests_passed",
        "Tests_timedout",
        "Tests_failed",
        "Tests_exception",
        "Merge_running",
    ],
)


def write_cache_merge_status(
    status: MERGE_STATES, runtime: float, explanation: str, cache_file: str
):
    """Writes the result of a test to a cache file.
    Args:
        status (MERGE_STATES): The status of the merge.
        runtime (float): The runtime of the merge.
        explanation (str): The explanation of the merge.
    """
    with open(cache_file + ".txt", "w") as f:
        f.write(status.name + "\n" + str(runtime))
    with open(cache_file + "_explanation.txt", "w") as f:
        f.write(explanation)


def read_cache_merge_status(cache_file: str) -> Tuple[MERGE_STATES, float, str]:
    """Reads the result of a test from a cache file.
    Args:
        cache_file (str): Path to the cache file.
    Returns:
        MERGE_STATES: The status of the merge.
        float: The runtime of the merge.
        str: The explanation of the merge.
    """
    with open(cache_file + ".txt", "r") as f:
        status_name = f.readline().strip()
        status = MERGE_STATES[status_name]
        runtime = float(f.readline().strip())
    if os.path.isfile(cache_file + "_explanation.txt"):
        with open(cache_file + "_explanation.txt", "r") as f:
            explanation = "".join(f.readlines())
    else:
        explanation = "No explanation file found."
    return status, runtime, explanation


def write_cache_diff_status(status: bool, cache_file: str):
    """Writes the result of the diff to a cache file.
    Args:
        status (int): The status of the diff.
    """
    with open(cache_file + ".txt", "w") as f:
        f.write(str(status))


def read_cache_diff_status(cache_file: str) -> bool:
    """Reads the result of the diff in the cache file.
    Args:
        cache_file (str): Path to the cache file.
    Returns:
        int: The status of the diff.
    """
    with open(cache_file + ".txt", "r") as f:
        status = f.readline()
    status = bool(status)
    return status


def merge_commits(
    repo_dir: str, left: str, right: str, merging_method: str
) -> Tuple[MERGE_STATES, float, str]:
    """Merges two commits in a repository.
    Args:
        repo_dir (str): Path to the directory containing the repo.
        left (str): Left commit.
        right (str): Right commit.
        merging_method (str): Name of the merging method to use.
    Returns:
        MERGE_STATES: The status of the merge.
        float: The runtime of the merge.
        str: The explanation of the merge.
    """
    try:
        repo = git.repo.Repo(repo_dir)
        repo.remote().fetch()
        repo.git.checkout(left, force=True)
        repo.submodule_update()
        repo.git.checkout("-b", LEFT_BRANCH_NAME, force=True)
        repo.git.checkout(right, force=True)
        repo.submodule_update()
        repo.git.checkout("-b", RIGHT_BRANCH_NAME, force=True)
        merge_status = MERGE_STATES.Merge_running
        explanation = "Merge running"
        runtime = -1
        start = time.time()
        p = subprocess.Popen(  # pylint: disable=consider-using-with
            [
                "src/scripts/merge_tools/" + merging_method + ".sh",
                repo_dir,
                LEFT_BRANCH_NAME,
                RIGHT_BRANCH_NAME,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        p.wait(timeout=TIMEOUT_MERGE)
        if p.returncode:
            merge_status = MERGE_STATES.Merge_failed
            explanation = "Merge Failed"
        else:
            merge_status = MERGE_STATES.Merge_success
            explanation = ""
        runtime = time.time() - start
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)  # type: ignore
        merge_status = MERGE_STATES.Merge_timedout
        explanation = "Timeout during merge"
        runtime = -1
    except Exception as e:
        merge_status = MERGE_STATES.Merge_exception
        explanation = str(e)
        runtime = -1
    return merge_status, runtime, explanation


def check_missing_cache_entry(
    cache_dir: str,
    merge_id: str,
    merging_method: str,
):
    """Checks if a cache entry is missing for a given merge and merging method.
    Args:
        cache_dir (str): Path to the cache directory.
        merge_id (str): ID name of the merge.
        merging_method (str): Name of the merging method.
    Returns:
        bool: True if a cache entry is missing, False otherwise.
    """
    prefix = os.path.join(cache_dir, "merge_diff_results", merge_id)
    cache_file = prefix + merging_method
    if not os.path.isfile(cache_file + ".txt"):
        return True
    for merging_method1 in MERGE_TOOLS:
        if merging_method1 == merging_method:
            continue
        cache_file = prefix + merging_method + "_" + merging_method1
        cache_file2 = prefix + merging_method1 + "_" + merging_method
        if not (
            os.path.isfile(cache_file + ".txt") or os.path.isfile(cache_file2 + ".txt")
        ):
            return True
    return False


def merge_and_test(  # pylint: disable=R0912,R0915,R0914
    args: Tuple[str, str, str, str, str, str]
) -> dict:
    """Merges a repo and executes its tests.
    Args:
        repo_name (str): Name of the repo, in "ORGANIZATION/REPO" format.
        left (str): Left parent hash of the merge.
        right (str): Right parent hash of the merge.
        base (str): Base parent hash of the merge.
        merge (str): Name of the merge.
        cache_dir (str): Path to the cache directory.
    Returns:
        dict: A dictionary containing the results of the tests and the comparison of the
            different merging methods.
    """
    repo_name, left, right, base, merge, cache_dir = args
    merge_id = "_".join([repo_name.split("/")[1], left, right, base, merge, ""])
    results_merging = {}
    repo_dir = os.path.join("repos/", repo_name)
    work_dir = os.path.join(WORKDIR, uuid.uuid4().hex)

    # Merge the commits using the different merging methods.
    for merging_method in MERGE_TOOLS:
        if check_missing_cache_entry(cache_dir, merge_id, merging_method):
            # The repo will be copied here, then work done in the copy.
            repo_dir_copy = os.path.join(work_dir, merging_method, "repo")
            shutil.copytree(repo_dir, repo_dir_copy)
            merge_status, runtime, explanation = merge_commits(
                repo_dir_copy, left, right, merging_method
            )
            results_merging[merging_method] = (
                merge_status,
                runtime,
                explanation,
                repo_dir_copy,
            )

    # Compare the results of the different merging methods.
    results = {}
    for idx, merging_method1 in enumerate(MERGE_TOOLS):
        merge_status1, _, _, path_merge_method1 = results_merging[merging_method1]
        for merging_method2 in MERGE_TOOLS[(idx + 1) :]:
            cache_file = os.path.join(
                cache_dir,
                "merge_diff_results",
                merge_id + merging_method1 + "_" + merging_method2,
            )
            if os.path.isfile(cache_file + ".txt"):
                status = read_cache_diff_status(cache_file)
                results[(merging_method1, merging_method2)] = status
                continue
            merge_status2, _, _, path_merge_method2 = results_merging[merging_method2]
            if (
                merge_status1 == MERGE_STATES.Merge_success
                and merge_status2 == MERGE_STATES.Merge_success
            ):
                command = f"diff -x .git* -r {path_merge_method1} {path_merge_method2}"
                with subprocess.Popen(command.split()) as process:
                    process.wait()
                    status = process.returncode == 0
            else:
                status = False
            results[(merging_method1, merging_method2)] = status
            write_cache_diff_status(status, cache_file)

    # Test the merged repos.
    for merging_method in MERGE_TOOLS:
        cache_file = os.path.join(
            cache_dir,
            "merge_test_results",
            merge_id + merging_method,
        )
        if os.path.isfile(cache_file + ".txt"):
            status, runtime, _ = read_cache_merge_status(cache_file)
            results[merging_method] = (status, runtime)
            continue
        merge_status, runtime, explanation, repo_dir_copy = results_merging[
            merging_method
        ]
        if merge_status == MERGE_STATES.Merge_success:
            try:
                test_status, explanation = repo_test(repo_dir_copy, TIMEOUT_TESTING)
                if test_status == TEST_STATE.Tests_passed:
                    merge_status = MERGE_STATES.Tests_passed
                elif test_status == TEST_STATE.Tests_timedout:
                    merge_status = MERGE_STATES.Tests_timedout
                else:
                    merge_status = MERGE_STATES.Tests_failed
                print(
                    repo_name + " " + merging_method + " testing with result:",
                    merge_status.name,
                )
            except Exception as e:
                merge_status = MERGE_STATES.Tests_exception
                explanation = str(e)
                print(
                    repo_name,
                    merging_method,
                    base,
                    "Exception during testing of the merge. Exception:\n",
                    e,
                )

        if STORE_SCRATCH:
            dst_name = os.path.join(SCRATCH_DIR, merge_id + merging_method)
            if os.path.isdir(dst_name):
                shutil.rmtree(dst_name, onerror=del_rw)
            repo_dir_copy_merging_method = os.path.join(repo_dir_copy, merging_method)
            if os.path.isdir(repo_dir_copy_merging_method):
                shutil.copytree(repo_dir_copy_merging_method, dst_name)

        if not STORE_WORKDIR:
            shutil.rmtree(work_dir, onerror=del_rw)

        write_cache_merge_status(merge_status, runtime, explanation, cache_file)
        results[merging_method] = (merge_status, runtime)
    return results


if __name__ == "__main__":
    print("merge_tester: Start")
    Path("repos").mkdir(parents=True, exist_ok=True)
    Path(WORKDIR).mkdir(parents=True, exist_ok=True)
    Path(SCRATCH_DIR).mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser()
    parser.add_argument("--valid_repos_csv", type=str)
    parser.add_argument("--merges_path", type=str)
    parser.add_argument("--output_file", type=str)
    parser.add_argument("--cache_dir", type=str, default="cache/")
    args = parser.parse_args()
    Path(os.path.join(args.cache_dir, "merge_test_results")).mkdir(
        parents=True, exist_ok=True
    )
    Path(os.path.join(args.cache_dir, "merge_diff_results")).mkdir(
        parents=True, exist_ok=True
    )
    df = pd.read_csv(args.valid_repos_csv, index_col="idx")

    print("merge_tester: Building Function Arguments")
    # Function arguments: (repo_name, left, right, base, merge)
    args_merges = []
    for _, repository_data in tqdm(df.iterrows(), total=len(df)):
        merge_list_file = os.path.join(
            args.merges_path, repository_data["repository"].split("/")[1] + ".csv"
        )
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(merge_list_file, index_col=0)
        for _, merge_data in merges.iterrows():
            if merge_data["parent test"] != TEST_STATE.Tests_passed.name:
                continue
            for merge_tool_idx, merge_tool in enumerate(MERGE_TOOLS):
                args_merges.append(
                    (
                        repository_data["repository"],
                        merge_data["left"],
                        merge_data["right"],
                        merge_data["base"],
                        merge_data["merge"],
                        args.cache_dir,
                    )
                )

    print("merge_tester: Finished Building Function Arguments")

    print("merge_tester: Number of merges:", len(args_merges))
    print("merge_tester: Started Testing")
    cpu_count = os.cpu_count() or 1
    processes_used = cpu_count - 2 if cpu_count > 3 else cpu_count
    with multiprocessing.Pool(processes=processes_used) as pool:
        r = list(
            pool.imap(merge_and_test, tqdm(args_merges, total=len(args_merges))),
        )
    print("merge_tester: Finished Testing")
    print("merge_tester: Building Output")

    output = []
    for _, repository_data in tqdm(df.iterrows(), total=len(df)):
        merge_list_file = os.path.join(
            args.merges_path, repository_data["repository"].split("/")[1] + ".csv"
        )
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(merge_list_file, index_col=0)

        # Initialize new columns
        merges["repo_name"] = [repository_data["repository"] for i in merges.iterrows()]
        merges = merges.reindex(columns=merges.columns.tolist() + MERGE_TOOLS)
        merges = merges.reindex(
            columns=merges.columns.tolist()
            + [
                "Equivalent " + merge_tool + " " + merge_tool2
                for idx, merge_tool in enumerate(MERGE_TOOLS)
                for merge_tool2 in MERGE_TOOLS[(idx + 1) :]
            ]
        )
        merges = merges.reindex(
            columns=merges.columns.tolist()
            + [merge_tool + " runtime" for merge_tool in MERGE_TOOLS]
        )

        for merge_idx, merge_data in merges.iterrows():
            if merge_data["parent test"] != TEST_STATE.Tests_passed.name:
                continue
            results = merge_and_test(
                (  # type: ignore
                    repository_data["repository"],
                    merge_data["left"],
                    merge_data["right"],
                    merge_data["base"],
                    merge_data["merge"],
                    args.cache_dir,
                )
            )
            for merge_tool_idx, merge_tool in enumerate(MERGE_TOOLS):
                merges.at[merge_idx, merge_tool] = results[merge_tool][0].name
                merges.at[merge_idx, merge_tool + " runtime"] = results[merge_tool][1]
                for merge_tool2 in MERGE_TOOLS[(merge_tool_idx + 1) :]:
                    merges.at[
                        merge_idx, "Equivalent " + merge_tool + " " + merge_tool2
                    ] = results[(merge_tool, merge_tool2)]
        output.append(merges)
    output = pd.concat(output, ignore_index=True)
    output.sort_values(by=["repo_name", "left", "right", "base", "merge"], inplace=True)
    output.reset_index(drop=True, inplace=True)
    output.to_csv(args.output_file, index_label="idx", columns=list(output.columns))
    print("merge_tester: Finished Building Output")
    print("merge_tester: Number of analyzed merges ", len(output))
    print("merge_tester: Done")
