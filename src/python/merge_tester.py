#!/usr/bin/env python3
"""Perform and test merges with different merge tools.

usage: python3 merge_tester.py --repos_csv <path_to_repos.csv>
                               --merges_path <path_to_merges_directory>
                               --output_path <output_path>

This script takes a csv of repos and a csv of merges and performs the merges with
the different merging tools. The input repositories should contain a repo_name 
column in format "ORGANIZATION/REPO". The merges csv should contain the following
columns: "left", "right", "base", "merge", "parent test". The "parent test" column
should contain the result of the test of the parent merge. The script will then
perform the merges and test the resulting repositories. The results of the merges
and the tests are stored in the output csv. The output csv will contain the same
columns as the input csv, plus the following columns: "repo_name", "merge_tool",
"merge_state", "run_time", "Equivalent merge_tool merge_tool2",
"merge_tool run_time". The "merge_state" column contains the result of the merge
and the "run_time" column contains the run time of the merge, in seconds. The
"Equivalent merge_tool merge_tool2" column contains the result of the diff between
the repositories resulting from the merge_tool and merge_tool2.
"""

import subprocess
import shutil
import os
import copy
import time
import multiprocessing
import argparse
from pathlib import Path
from functools import partialmethod
from enum import Enum
from typing import Tuple, Dict, List
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
STORE_WORKDIR = True
TIMEOUT_MERGE = 15 * 60  # 15 Minutes
TIMEOUT_TESTING = 45 * 60  # 45 Minutes
BRANCH_BASE_NAME = "___MERGE_TESTER"
LEFT_BRANCH_NAME = BRANCH_BASE_NAME + "_LEFT"
RIGHT_BRANCH_NAME = BRANCH_BASE_NAME + "_RIGHT"
MERGE_TOOL = [
    "gitmerge-ort",
    "gitmerge-ort-ignorespace",
    "gitmerge-recursive-patience",
    "gitmerge-recursive-minimal",
    "gitmerge-recursive-histogram",
    "gitmerge-recursive-myers",
    "gitmerge-resolve",
    "spork",
    "intellimerge",
]

MERGE_STATE = Enum(
    "MERGE_STATE",
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
    """Class to store the result of a merge."""

    def __init__(
        self,
        merge_tool: str,
        cache_merge_status_prefix: str,
        cache_diff_status_prefix: str,
        merge_tools: List[str],
    ):
        self.merge_tool = merge_tool
        self.merge_tools = merge_tools
        self.explanation: str = ""
        self.run_time = -1
        self.merge_state_cache_path = Path(
            cache_merge_status_prefix + merge_tool + ".txt"
        )
        self.merge_state_explanation_cache_path = Path(
            cache_merge_status_prefix + merge_tool + "_explanation.txt"
        )
        self.merge_path: str = ""
        self.merge_state: MERGE_STATE = MERGE_STATE.Merge_running
        self.diff_merge_result: Dict[str, bool] = {}
        self.diff_merge_result_cache_path: Dict[str, Path] = {}
        self.diff_merge_explanation: Dict[str, str] = {}
        for merge_tool2 in merge_tools:
            self.diff_merge_explanation[merge_tool2] = ""
            if merge_tool2 < merge_tool:
                self.diff_merge_result_cache_path[merge_tool2] = Path(
                    cache_diff_status_prefix + merge_tool + "_" + merge_tool2 + ".txt"
                )
                self.diff_merge_explanation_cache_path = str(
                    cache_diff_status_prefix
                    + merge_tool
                    + "_"
                    + merge_tool2
                    + "_explanation.txt"
                )

            elif merge_tool2 > merge_tool:
                self.diff_merge_result_cache_path[merge_tool2] = Path(
                    cache_diff_status_prefix + merge_tool2 + "_" + merge_tool + ".txt"
                )
                self.diff_merge_explanation_cache_path = str(
                    cache_diff_status_prefix
                    + merge_tool2
                    + "_"
                    + merge_tool
                    + "_explanation.txt"
                )

    def write_cache_merge_status(self):
        """Writes the merge status to a cache file."""
        with open(self.merge_state_cache_path, "w") as f:
            f.write(self.merge_state.name + "\n" + str(self.run_time))
        with open(self.merge_state_explanation_cache_path, "w") as f:
            f.write(self.explanation)

    def read_cache_merge_status(self) -> bool:
        """Reads the result of a test from a cache file.
        Returns:
            bool: True if the cache file exists, False otherwise.
        """
        if os.path.isfile(self.merge_state_cache_path):
            with open(self.merge_state_cache_path, "r") as f:
                status_name = f.readline().strip()
                self.merge_state = MERGE_STATE[status_name]
                self.run_time = float(f.readline().strip())
            if os.path.isfile(self.merge_state_explanation_cache_path):
                with open(self.merge_state_explanation_cache_path, "r") as f:
                    self.explanation = "".join(f.readlines())
            else:
                self.explanation = "No explanation file found."
            return True
        return False

    def write_cache_diff_status(self, merge_tool: str):
        """Writes the result of the diff to a cache file.
        Args:
            merge_tool (str): Name of the merge tool of the diff.
        """
        with open(self.diff_merge_result_cache_path[merge_tool], "w") as f:
            f.write(str(self.diff_merge_result[merge_tool]))
        with open(self.diff_merge_explanation_cache_path, "w") as f:
            f.write(self.diff_merge_explanation[merge_tool])

    def read_cache_diff_status(self, merge_tool: str):
        """Reads the result of the diff in the cache file.
        Args:
            merge_tool (str): Name of the merge tool of the diff.
        Returns:
            bool: True if the cache file exists, False otherwise.
        """
        if os.path.isfile(self.diff_merge_result_cache_path[merge_tool]):
            with open(self.diff_merge_result_cache_path[merge_tool], "r") as f:
                status = f.readline()
            status = status.strip() == "True"
            self.diff_merge_result[merge_tool] = status
            if os.path.isfile(self.diff_merge_explanation_cache_path):
                with open(self.diff_merge_explanation_cache_path, "r") as f:
                    self.diff_merge_explanation[merge_tool] = "".join(f.readlines())
            return True
        return False

    def check_missing_cache_entry(self, check_diff: bool) -> bool:
        """Checks if a cache entry is missing for a given merge.
        Args:
            merge_entry (MergeEntry): The merge entry to check.
        Returns:
            bool: True if a cache entry is missing, False otherwise.
        """
        if not os.path.isfile(self.merge_state_cache_path):
            return True
        if not check_diff:
            return False
        for merge_tool2 in self.merge_tools:
            if merge_tool2 != self.merge_tool and not os.path.isfile(
                self.diff_merge_result_cache_path[merge_tool2]
            ):
                return True
        return False


def merge_commits(
    repo_dir: str, left: str, right: str, merging_method: str
) -> Tuple[MERGE_STATE, float, str]:
    """Merges two commits in a repository.
    Args:
        repo_dir (str): Path to the directory containing the repo.
        left (str): Left commit.
        right (str): Right commit.
        merging_method (str): Name of the merging method to use.
    Returns:
        MERGE_STATE: The status of the merge.
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
        merge_status = MERGE_STATE.Merge_running
        explanation = "Merge running"
        run_time = -1
        start = time.time()
        p = subprocess.run(  # pylint: disable=consider-using-with
            [
                "src/scripts/merge_tools/" + merging_method + ".sh",
                repo_dir,
                LEFT_BRANCH_NAME,
                RIGHT_BRANCH_NAME,
            ],
            capture_output=True,
            timeout=TIMEOUT_MERGE,
            check=False,
        )
        if p.returncode:
            explanation = "STDOUT:\n" + p.stdout.decode("utf-8")
            explanation += "\nSTDERR:\n" + p.stderr.decode("utf-8")
            merge_status = MERGE_STATE.Merge_failed
        else:
            merge_status = MERGE_STATE.Merge_success
            explanation = ""
        run_time = time.time() - start
    except subprocess.TimeoutExpired as timeErr:
        merge_status = MERGE_STATE.Merge_timedout
        explanation = "Timeout\n"
        if timeErr.stdout:
            explanation = "STDOUT:\n" + timeErr.stdout.decode("utf-8")
        if timeErr.stderr:
            explanation += "\nSTDERR:\n" + timeErr.stderr.decode("utf-8")
        run_time = -1
    except Exception as e:
        merge_status = MERGE_STATE.Merge_exception
        explanation = str(e)
        run_time = -1
    return merge_status, run_time, explanation


def merge_and_test(  # pylint: disable=R0912,R0915,R0914
    args: Tuple[str, str, str, str, str, str, bool, List[str]]
) -> Dict[str, MergeEntry]:
    """Merges a repo and executes its tests.
    Args:
        repo_name (str): Name of the repo, in "ORGANIZATION/REPO" format.
        left (str): Left parent hash of the merge.
        right (str): Right parent hash of the merge.
        base (str): Base parent hash of the merge.
        merge (str): Name of the merge.
        cache_dir (str): Path to the cache directory.
        merge_tools (List[str]): List of merge tools to analyze.
    Returns:
        dict: A dictionary containing the results of the tests and the comparison of the
            different merging methods.
    """
    repo_name, left, right, base, merge, cache_dir, check_diff, merge_tools = args
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
            merge_tools=merge_tools,
        )
        for merge_tool in merge_tools
    }
    # Merge the commits using the different merging methods.
    for merging_method in merge_tools:
        if result[merging_method].check_missing_cache_entry(check_diff=check_diff):
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
    if check_diff:
        for merge_tool1 in merge_tools:
            for merge_tool2 in merge_tools:
                if merge_tool1 == merge_tool2 or result[
                    merge_tool1
                ].read_cache_diff_status(merge_tool2):
                    continue
                if (
                    result[merge_tool1].merge_state == MERGE_STATE.Merge_success
                    and result[merge_tool2].merge_state == MERGE_STATE.Merge_success
                ):
                    command = (
                        "diff -x .git* -r "
                        + result[merge_tool1].merge_path
                        + " "
                        + result[merge_tool2].merge_path
                    )
                    process = subprocess.run(command.split(), capture_output=True)
                    result[merge_tool1].diff_merge_explanation[merge_tool2] = (
                        "Running command: "
                        + command
                        + "\n STDOUT:\n"
                        + process.stdout.decode("utf-8")
                        + "\n STDERR:\n"
                        + process.stderr.decode("utf-8")
                    )
                    status = process.returncode == 0
                else:
                    result[merge_tool1].diff_merge_explanation[
                        merge_tool2
                    ] = "Merge failed for one of the merging methods."
                    status = False
                result[merge_tool1].diff_merge_result[merge_tool2] = status
                result[merge_tool1].write_cache_diff_status(merge_tool2)
    # Test the merged repos.
    for merging_method in merge_tools:
        if result[merging_method].read_cache_merge_status():
            print(
                f"Read from cache {repo_name} {left} {right}\
                     {merging_method} result: {result[merging_method].merge_state.name}"
            )
            continue
        if result[merging_method].merge_state == MERGE_STATE.Merge_success:
            print(f"Testing Merge {repo_name} {left} {right} {merging_method}")
            try:
                test_status, explanation = repo_test(
                    result[merging_method].merge_path, TIMEOUT_TESTING
                )
                if test_status == TEST_STATE.Tests_passed:
                    result[merging_method].merge_state = MERGE_STATE.Tests_passed
                elif test_status == TEST_STATE.Tests_timedout:
                    result[merging_method].merge_state = MERGE_STATE.Tests_timedout
                else:
                    result[merging_method].merge_state = MERGE_STATE.Tests_failed
            except Exception as e:
                result[merging_method].merge_state = MERGE_STATE.Tests_exception
                explanation = str(e)
            print(
                f"Finished Testing Merge {repo_name} {left}\
                      {right} {merging_method} result: {result[merging_method].merge_state}"
            )

        if STORE_SCRATCH:
            dst_name = os.path.join(SCRATCH_DIR, merge_id + merging_method)
            if os.path.isdir(dst_name):
                shutil.rmtree(dst_name, onerror=del_rw)
            repo_dir_copy_merging_method = os.path.join(
                result[merging_method].merge_path, merging_method
            )
            if os.path.isdir(repo_dir_copy_merging_method):
                shutil.copytree(repo_dir_copy_merging_method, dst_name)
        print(
            f"Writing Testing Merge {repo_name} {left} \
                {right} {merging_method} result: {result[merging_method].merge_state}"
        )
        result[merging_method].write_cache_merge_status()
    if not STORE_WORKDIR:
        shutil.rmtree(work_dir, onerror=del_rw)
    return result


if __name__ == "__main__":
    print("merge_tester: Start")
    Path("repos").mkdir(parents=True, exist_ok=True)
    Path(WORKDIR).mkdir(parents=True, exist_ok=True)
    Path(SCRATCH_DIR).mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--valid_repos_csv", type=str, default="results2/valid_repos.csv"
    )
    parser.add_argument("--merges_path", type=str, default="results2/merge_valid")
    parser.add_argument("--output_file", type=str, default="results2")
    parser.add_argument("--cache_dir", type=str, default="cache/")
    # Check diff flag
    parser.add_argument("-diff", action="store_true")
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
            if args.diff:
                args_merges.append(
                    (
                        repository_data["repository"],
                        merge_data["left"],
                        merge_data["right"],
                        merge_data["base"],
                        merge_data["merge"],
                        args.cache_dir,
                        args.diff,
                        MERGE_TOOL,
                    )
                )
            else:
                for merge_tool in MERGE_TOOL:
                    merge_and_test(
                        (
                            repository_data["repository"],
                            merge_data["left"],
                            merge_data["right"],
                            merge_data["base"],
                            merge_data["merge"],
                            args.cache_dir,
                            args.diff,
                            [merge_tool],
                        )
                    )

    print("merge_tester: Finished Building Function Arguments")

    print("merge_tester: Number of merges:", len(args_merges))
    print("merge_tester: Started Testing")
    # cpu_count = os.cpu_count() or 1
    # processes_used = cpu_count - 2 if cpu_count > 3 else cpu_count
    # with multiprocessing.Pool(processes=processes_used) as pool:
    #     r = list(
    #         pool.imap(merge_and_test, tqdm(args_merges, total=len(args_merges))),
    #     )
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
        merges = merges.reindex(columns=merges.columns.tolist() + MERGE_TOOL)
        merges = merges.reindex(
            columns=merges.columns.tolist()
            + [
                "Equivalent " + merge_tool + " " + merge_tool2
                for idx, merge_tool in enumerate(MERGE_TOOL)
                for merge_tool2 in MERGE_TOOL[(idx + 1) :]
            ]
        )
        merges = merges.reindex(
            columns=merges.columns.tolist()
            + [merge_tool + " run_time" for merge_tool in MERGE_TOOL]
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
                    args.diff,
                    MERGE_TOOL,
                )
            )
            for merge_tool_idx, merge_tool in enumerate(MERGE_TOOL):
                merges.at[merge_idx, merge_tool] = results[merge_tool].merge_state.name
                merges.at[merge_idx, merge_tool + " run_time"] = results[
                    merge_tool
                ].run_time
                if args.diff:
                    for merge_tool2 in MERGE_TOOL[(merge_tool_idx + 1) :]:
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
