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
import traceback
from pathlib import Path
from functools import partialmethod

from validate_repos import repo_test, del_rw
from tqdm import tqdm  # shows a progress meter as a loop runs
import pandas as pd
import git.repo

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)


SCRATCH_DIR = "scratch/"
# If true, the merged repository under SCRATCH_DIR will be retained.
# Otherwise, it is deleted after its tests are run.
STORE_SCRATCH = False
WORKDIR = ".workdir/"
# If true, the working directories in WORKDIR will be deleted.
# Otherwise, it is deleted after its tests are run.
STORE_WORKDIR = False
CACHE = "cache/merge_test_results/"
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


def write_cache(status, runtime, explanation, cache_file):
    """Writes the result of a test to a cache file.
    Args:
        status (str): Test result.
        runtime (float): Runtime of the test.
        explanation (str): Explanation of the test result.
        cache_file (str): Path to the cache file.
    """
    with open(cache_file, "w") as f:
        f.write(status + "\n" + str(runtime) + "\n" + explanation)


def read_cache(cache_file):
    """Reads the result of a test from a cache file.
    Args:
        cache_file (str): Path to the cache file.
    Returns:
        str: Test result.
        float: Runtime of the test.
        str: Explanation of the test result.
    """
    with open(cache_file, "r") as f:
        status = f.readline().strip()
        runtime = float(f.readline().strip())
        explanation = f.readline().strip()
    return status, runtime, explanation


def merge_and_test(
    args,
):  # pylint: disable=too-many-locals, disable=too-many-statements
    """Merges a repo and executes its tests.
    Args:
        merging_method (str): Name of the merging method to use.
        repo_name (str): Name of the repo, in "ORGANIZATION/REPO" format.
        left (str): Left parent hash of the merge.
        right (str): Right parent hash of the merge.
        base (str): Base parent hash of the merge.
        merge (str): Name of the merge.
    Returns:
        str: Test result of merge. Possible values are:
            "Failure merge" if the merge failed.
            "Timeout merge" if the merge timed out.
            "Failure tests" if the tests failed.
            "Success tests" if the merge and tests succeeded.
            "Timeout tests" if the tests timed out.
            "Failure merge general exception" if an exception occurred during the merge.
            "Failure testing exception" if an exception occurred during the tests.
            "Failure general exception during handling of the repository" if an exception
                occurred during the handling of the repository.
        float: Runtime to execute the merge.
    """
    merging_method, repo_name, left, right, base, merge = args
    cache_file = os.path.join(
        CACHE,
        repo_name.split("/")[1]
        + "_"
        + left
        + "_"
        + right
        + "_"
        + base
        + "_"
        + merge
        + "_"
        + merging_method,
    )
    if os.path.isfile(cache_file):
        status, runtime, _ = read_cache(cache_file)
        return status, runtime
    # Variable `merge_status` is returned by this routine.
    repo_dir = os.path.join("repos/", repo_name)
    process = multiprocessing.current_process()
    pid = str(process.pid)
    # The repo will be copied here, then work done in the copy.
    repo_dir_copy = os.path.join(WORKDIR, pid, "repo")
    try:
        if os.path.isdir(repo_dir_copy):
            shutil.rmtree(repo_dir_copy, onerror=del_rw)

        shutil.copytree(repo_dir, repo_dir_copy + "/" + merging_method)
        repo = git.repo.Repo(repo_dir_copy + "/" + merging_method)
        repo.remote().fetch()
        repo.submodule_update()
        repo.git.checkout(left, force=True)
        repo.git.checkout("-b", LEFT_BRANCH_NAME, force=True)
        repo.git.checkout(right, force=True)
        repo.git.checkout("-b", RIGHT_BRANCH_NAME, force=True)
        start = time.time()
        try:
            p = subprocess.run(
                [
                    "src/scripts/merge_tools/" + merging_method + ".sh",
                    repo_dir_copy + "/" + merging_method,
                    LEFT_BRANCH_NAME,
                    RIGHT_BRANCH_NAME,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=TIMEOUT_MERGE,
            )
            merge_status = "Failure merge" if p.returncode else "Success merge"
            explanation = ""
            runtime = time.time() - start
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)  # type: ignore
            runtime = time.time() - start
            merge_status = "Timeout merge"
            explanation = "Timeout during merge"
        except Exception as e:
            merge_status = "Failure merge general exception"
            explanation = str(e)
            runtime = -1
            print(
                repo_name,
                merging_method,
                base,
                "Exception during merge. Exception:\n",
                e,
            )
        try:
            if merge_status == "Success merge":
                merge_status, explanation = repo_test(
                    repo_dir_copy + "/" + merging_method, TIMEOUT_TESTING
                )
                print(
                    repo_name + " " + merging_method + " testing with result:",
                    merge_status,
                )
                merge_status += " test"
        except Exception as e:
            merge_status = "Failure testing exception"
            explanation = str(e)
            print(
                repo_name,
                merging_method,
                base,
                "Exception during testing of the merge. Exception:\n",
                e,
            )
    except Exception as e:
        merge_status = "Failure general exception during handling of the repository"
        explanation = str(e)
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
        dst_name = os.path.join(
            SCRATCH_DIR, "_".join([repo_name, left, right, base, merging_method])
        )
        if os.path.isdir(dst_name):
            shutil.rmtree(dst_name, onerror=del_rw)
        repo_dir_copy_merging_method = os.path.join(repo_dir_copy, merging_method)
        if os.path.isdir(repo_dir_copy_merging_method):
            shutil.copytree(repo_dir_copy_merging_method, dst_name)

    if not STORE_WORKDIR:
        shutil.rmtree(repo_dir_copy, onerror=del_rw)

    write_cache(merge_status, runtime, explanation, cache_file)
    return merge_status, runtime


if __name__ == "__main__":
    print("merge_tester: Start")
    Path("repos").mkdir(parents=True, exist_ok=True)
    Path(CACHE).mkdir(parents=True, exist_ok=True)
    Path(WORKDIR).mkdir(parents=True, exist_ok=True)
    Path(SCRATCH_DIR).mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_csv", type=str)
    parser.add_argument("--merges_path", type=str)
    parser.add_argument("--output_file", type=str)
    args = parser.parse_args()
    df = pd.read_csv(args.repos_csv)

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
            if merge_data["parent test"] != "Success":
                continue
            for merge_tool_idx, merge_tool in enumerate(MERGE_TOOLS):
                args_merges.append(
                    (
                        merge_tool,
                        repository_data["repository"],
                        merge_data["left"],
                        merge_data["right"],
                        merge_data["base"],
                        merge_data["merge"],
                    )
                )

    print("merge_tester: Finished Building Function Arguments")

    print("merge_tester: Number of merges:", len(args_merges))
    print("merge_tester: Started Testing")
    cpu_count = os.cpu_count() or 1
    processes_used = cpu_count - 2 if cpu_count > 3 else cpu_count
    with multiprocessing.Pool(processes=processes_used) as pool:
        r = list(
            tqdm(
                pool.imap(merge_and_test, args_merges),
                total=len(args_merges),
                miniters=1,
            )
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
        for merge_tool in MERGE_TOOLS:
            merges[merge_tool] = [-10 for i in merges.iterrows()]
        for merge_tool in MERGE_TOOLS:
            merges[merge_tool + " runtime"] = [-10 for i in merges.iterrows()]

        for merge_idx, merge_data in merges.iterrows():
            if merge_data["parent test"] != "Success":
                continue

            for merge_tool_idx, merge_tool in enumerate(MERGE_TOOLS):
                status, runtime = merge_and_test(
                    (
                        merge_tool,
                        repository_data["repository"],
                        merge_data["left"],
                        merge_data["right"],
                        merge_data["base"],
                        merge_data["merge"],
                    )
                )
                merges.at[merge_idx, merge_tool] = status
                merges.at[merge_idx, merge_tool + " runtime"] = runtime
        output.append(merges)
    output = pd.concat(output, ignore_index=True)
    output.to_csv(args.output_file)
    print("merge_tester: Finished Building Output")
    print("merge_tester: Number of analyzed merges ", len(output))
    print("merge_tester: Done")
