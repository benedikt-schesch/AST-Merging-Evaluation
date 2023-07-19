#!/usr/bin/env python3
"""Perform and test merges with different merge tools.

usage: python3 merge_tester.py --repos_csv <path_to_repos.csv>
                               --merges_path <path_to_merges_directory>
                               --output_path <output_path>

This script takes a csv of repos and a csv of merges and performs the merges with
the different merging tools. Each merge is then tested.
An output file is generated with the results for each merge.
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
from typing import Tuple, Dict
import uuid
from dataclasses import dataclass

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


class MergeEntry:
    merge_tool: str = ""
    merge_state_cache_path: str = ""
    merge_path: str = ""
    merge_state: MERGE_STATES = MERGE_STATES.Merge_running
    merge_state_explanation_cache_path: str = ""
    explanation: str = ""
    run_time: float = -1
    explanation: str = ""
    diff_merge_result: Dict[str, bool] = {}
    diff_merge_result_cache_path: Dict[str, str] = {}

    def __init__(
        self,
        merge_tool: str,
        cache_merge_status_prefix: str,
        cache_diff_status_prefix: str,
    ):
        self.merge_tool = merge_tool
        self.merge_state_cache_path = cache_merge_status_prefix + merge_tool + ".txt"
        self.merge_state_explanation_cache_path = (
            cache_merge_status_prefix + merge_tool + "_explanation.txt"
        )
        for merge_tool2 in MERGE_TOOLS:
            if merge_tool2 < merge_tool:
                self.diff_merge_result_cache_path[merge_tool2] = (
                    cache_diff_status_prefix + merge_tool + "_" + merge_tool2 + ".txt"
                )
            elif merge_tool2 > merge_tool:
                self.diff_merge_result_cache_path[merge_tool2] = (
                    cache_diff_status_prefix + merge_tool2 + "_" + merge_tool + ".txt"
                )


def write_cache_merge_status(merge_entry: MergeEntry):
    """Writes the result of a test to a cache file.
    Args:
        status (MERGE_STATES): The status of the merge.
        run_time (float): The run_time of the merge.
        explanation (str): The explanation of the merge.
    """
    with open(merge_entry.merge_state_cache_path,"w") as f:
        f.write(merge_entry.merge_state.name + "\n" + str(merge_entry.run_time))
    with open(merge_entry.merge_state_explanation_cache_path, "w") as f:
        f.write(merge_entry.explanation)


def read_cache_merge_status(merge_entry: MergeEntry) -> bool:
    """Reads the result of a test from a cache file.
    Args:
        merge_entry(MergeEntry): The merge entry to read the cache from.
    Returns:
        bool: True if the cache file exists, False otherwise.
    """
    if os.path.isfile(merge_entry.merge_state_cache_path):
        print("IN CACHE:", merge_entry.merge_state_cache_path)
        with open(merge_entry.merge_state_cache_path, "r") as f:
            status_name = f.readline().strip()
            merge_entry.merge_state = MERGE_STATES[status_name]
            merge_entry.run_time = float(f.readline().strip())
        if os.path.isfile(merge_entry.merge_state_explanation_cache_path):
            with open(merge_entry.merge_state_explanation_cache_path, "r") as f:
                merge_entry.explanation = "".join(f.readlines())
        else:
            merge_entry.explanation = "No explanation file found."
        return True
    return False


def write_cache_diff_status(status: bool, cache_file: str):
    """Writes the result of the diff to a cache file.
    Args:
        status (int): The status of the diff.
    """
    with open(cache_file, "w") as f:
        f.write(str(status))


def read_cache_diff_status(cache_file: str) -> bool:
    """Reads the result of the diff in the cache file.
    Args:
        cache_file (str): Path to the cache file.
    Returns:
        bool: The status of the diff.
    """
    with open(cache_file, "r") as f:
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
        float: The run_time of the merge.
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
        run_time = -1
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
        run_time = time.time() - start
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)  # type: ignore
        merge_status = MERGE_STATES.Merge_timedout
        explanation = "Timeout during merge"
        run_time = -1
    except Exception as e:
        merge_status = MERGE_STATES.Merge_exception
        explanation = str(e)
        run_time = -1
    return merge_status, run_time, explanation


def check_missing_cache_entry(merge_entry: MergeEntry) -> bool:
    """Checks if a cache entry is missing for a given merge.
    Args:
        merge_entry (MergeEntry): The merge entry to check.
    Returns:
        bool: True if a cache entry is missing, False otherwise.
    """
    if not os.path.isfile(merge_entry.merge_state_cache_path):
        return True
    for merge_tool2 in MERGE_TOOLS:
        if merge_tool2 != merge_entry.merge_tool and not os.path.isfile(
            merge_entry.diff_merge_result_cache_path[merge_tool2]
        ):
            return True
    return False


def merge_and_test(  # pylint: disable=R0912,R0915,R0914
    args: Tuple[str, str, str, str, str, str]
) -> Dict[str, MergeEntry]:
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
    repo_dir = os.path.join("repos/", repo_name)
    work_dir = os.path.join(WORKDIR, uuid.uuid4().hex)
    cache_merge_status_prefix = os.path.join(
        cache_dir,
        "merge_test_results",
        "_".join([repo_name.split("/")[1], left, right, base, merge, ""]),
    )
    cache_diff_status_prefix = os.path.join(
        cache_dir,
        "merge_diff_results",
        "_".join([repo_name.split("/")[1], left, right, base, merge, ""]),
    )

    result: Dict[str, MergeEntry] = {
        merge_tool: MergeEntry(
            merge_tool=merge_tool,
            cache_diff_status_prefix=cache_diff_status_prefix,
            cache_merge_status_prefix=cache_merge_status_prefix,
        )
        for merge_tool in MERGE_TOOLS
    }
    # Merge the commits using the different merging methods.
    for merging_method in MERGE_TOOLS:
        if check_missing_cache_entry(result[merging_method]):
            # The repo will be copied here, then work done in the copy.
            print(f"Merging {repo_name} {left} {right} with {merging_method}")
            repo_dir_copy = os.path.join(work_dir, merging_method, "repo")
            shutil.copytree(repo_dir, repo_dir_copy)
            merge_status, run_time, explanation = merge_commits(
                repo_dir_copy, left, right, merging_method
            )
            result[merging_method].merge_state = merge_status
            result[merging_method].merge_path = repo_dir_copy
            result[merging_method].explanation = explanation
            result[merging_method].run_time = run_time
    # Compare the results of the different merging methods.
    for merge_tool1 in MERGE_TOOLS:
        for merge_tool2 in MERGE_TOOLS:
            if os.path.isfile(
                result[merge_tool1].diff_merge_result_cache_path[merge_tool2]
            ):
                status = read_cache_diff_status(
                    result[merge_tool1].diff_merge_result_cache_path[merge_tool2]
                )
                result[merge_tool1].diff_merge_result[merge_tool2] = status
                continue
            if (
                result[merge_tool1].merge_state == MERGE_STATES.Merge_success
                and result[merge_tool2].merge_state == MERGE_STATES.Merge_success
            ):
                command = f"diff -x .git* -r {result[merge_tool1].merge_path} {result[merge_tool2].merge_path}"
                process =  subprocess.run(command.split(),capture_output=True)
                status = process.returncode == 0
                if not status:
                    print(f"Diff {process.stdout} {process.stderr}")
            else:
                status = False
            result[merge_tool1].diff_merge_result[merge_tool2] = status
            write_cache_diff_status(
                status, result[merge_tool1].diff_merge_result_cache_path[merge_tool2]
            )
    # Test the merged repos.
    for merging_method in MERGE_TOOLS:
        if read_cache_merge_status(result[merging_method]):
            print(f"Read from cache {repo_name} {left} {right} {merging_method} result: {result[merging_method].merge_state.name}")
            continue
        if result[merging_method].merge_state == MERGE_STATES.Merge_success:
            print(f"Testing Merge {repo_name} {left} {right} {merging_method}")
            try:
                test_status, explanation = repo_test(
                    result[merging_method].merge_path, TIMEOUT_TESTING
                )
                if test_status == TEST_STATE.Tests_passed:
                    result[merging_method].merge_state = MERGE_STATES.Tests_passed
                elif test_status == TEST_STATE.Tests_timedout:
                    result[merging_method].merge_state = MERGE_STATES.Tests_timedout
                else:
                    result[merging_method].merge_state = MERGE_STATES.Tests_failed
            except Exception as e:
                result[merging_method].merge_state = MERGE_STATES.Tests_exception
                explanation = str(e)
            print(f"Finished Testing Merge {repo_name} {left} {right} {merging_method} result: {result[merging_method].merge_state}")

        if STORE_SCRATCH:
            dst_name = os.path.join(SCRATCH_DIR, merge_id + merging_method)
            if os.path.isdir(dst_name):
                shutil.rmtree(dst_name, onerror=del_rw)
            repo_dir_copy_merging_method = os.path.join(
                result[merging_method].merge_path, merging_method
            )
            if os.path.isdir(repo_dir_copy_merging_method):
                shutil.copytree(repo_dir_copy_merging_method, dst_name)
        print(f"Writing Testing Merge {repo_name} {left} {right} {merging_method} result: {result[merging_method].merge_state}")
        write_cache_merge_status(result[merging_method])
    if not STORE_WORKDIR:
        shutil.rmtree(work_dir, onerror=del_rw)
    return result


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
            + [merge_tool + " run_time" for merge_tool in MERGE_TOOLS]
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
                merges.at[merge_idx, merge_tool] = results[merge_tool].merge_state.name
                merges.at[merge_idx, merge_tool + " run_time"] = results[
                    merge_tool
                ].run_time
                for merge_tool2 in MERGE_TOOLS[(merge_tool_idx + 1) :]:
                    merges.at[
                        merge_idx, "Equivalent " + merge_tool + " " + merge_tool2
                    ] = results[merge_tool].diff_merge_result[merge_tool2]
        output.append(merges)
    output = pd.concat(output, ignore_index=True)
    output.sort_values(by=["repo_name", "left", "right", "base", "merge"], inplace=True)
    output.reset_index(drop=True, inplace=True)
    output.to_csv(args.output_file, index_label="idx", columns=list(output.columns))
    print("merge_tester: Finished Building Output")
    print("merge_tester: Number of analyzed merges ", len(output))
    print("merge_tester: Done")
