#!/usr/bin/env python3
""" Compare the results of two merge tools on the same merge.
usage: python3 merge_differ.py --result_csv <result_csv.csv>
                                --cache_dir <cache_dir>
This script compares the results of two merge tools on the same merge.
It outputs the diff of the two merge results.
"""

import os
import multiprocessing
import argparse
from pathlib import Path
from functools import partialmethod
from typing import Tuple
import random
import subprocess
import pandas as pd
from repo import Repository, MERGE_TOOL, TEST_STATE
from tqdm import tqdm

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore

TIMEOUT_TESTING_PARENT = 60 * 30  # 30 minutes
TIMEOUT_TESTING_MERGE = 60 * 45  # 45 minutes
N_RESTARTS = 3


def merge_differ(  # pylint: disable=too-many-locals
    args: Tuple[pd.Series, Path]
) -> None:
    """Tests the parents of a merge and in case of success, it tests the merge.
    Args:
        args (Tuple[pd.Series,Path]): A tuple containing the repository info and
                    the cache path.
    Returns:
        dict: The result of the test.
    """
    merge_data, cache_prefix = args
    repo_name = merge_data["repository"]
    left = merge_data["left"]
    right = merge_data["right"]

    for merge_tool1 in MERGE_TOOL:
        if merge_data[merge_tool1.name] not in (
            TEST_STATE.Tests_passed.name,
            TEST_STATE.Tests_failed.name,
        ):
            continue
        repo1 = Repository(repo_name, cache_prefix=cache_prefix)
        (
            merge_status1,
            merge_fingerprint1,
            left_fingreprint1,
            right_fingerprint1,
            _,
            _,
        ) = repo1.merge(
            tool=merge_tool1,
            left_commit=left,
            right_commit=right,
            timeout=-1,
        )
        assert merge_status1 == merge_data[merge_tool1.name]
        assert left_fingreprint1 == merge_data["left_tree_fingerprint"]
        assert right_fingerprint1 == merge_data["right_tree_fingerprint"]
        assert merge_fingerprint1 == merge_data[merge_tool1.name + "_merge_fingerprint"]
        if merge_fingerprint1 is None:
            continue
        for merge_tool2 in MERGE_TOOL:
            if merge_data[merge_tool2.name] not in (
                TEST_STATE.Tests_passed.name,
                TEST_STATE.Tests_failed.name,
            ):
                continue
            if (
                merge_data[merge_tool1.name + "_merge_fingerprint"]
                == merge_data[merge_tool2.name + "_merge_fingerprint"]
            ):
                continue
            repo2 = Repository(repo_name, cache_prefix=cache_prefix)
            (
                merge_status2,
                merge_fingerprint2,
                left_fingreprint2,
                right_fingerprint2,
                _,
                _,
            ) = repo2.merge(
                tool=merge_tool2,
                left_commit=left,
                right_commit=right,
                timeout=-1,
            )
            assert merge_status2 == merge_data[merge_tool2.name]
            assert left_fingreprint2 == merge_data["left_tree_fingerprint"]
            assert right_fingerprint2 == merge_data["right_tree_fingerprint"]
            assert (
                merge_fingerprint2
                == merge_data[merge_tool2.name + "_merge_fingerprint"]
            )
            if merge_fingerprint2 is None:
                continue
            diff_file = (
                cache_prefix
                / "merge_diffs"
                / diff_file_name(merge_fingerprint1, merge_fingerprint2)
            )
            diff_file.parent.mkdir(parents=True, exist_ok=True)
            if diff_file.exists():
                continue
            command = ["diff", "-u", "-r", "-x", "*/\\.git*"]
            command.append(str(repo1.repo_path))
            command.append(str(repo2.repo_path))
            with open(diff_file, "w") as f:
                subprocess.run(command, stdout=f, stderr=f)
            del repo2
        del repo1


def diff_file_name(sha1: str, sha2: str) -> Path:
    """Returns the name of the diff file.
    Args:
        sha1 (str): The first sha.
        sha2 (str): The second sha.
    Returns:
        Path: The name of the diff file.
    """
    if sha1 < sha2:
        return Path(sha1 + "_" + sha2 + ".txt")
    return Path(sha2 + "_" + sha1 + ".txt")


if __name__ == "__main__":
    print("merge_differ: Start")
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_csv", type=str)
    parser.add_argument("--cache_dir", type=str, default="cache/")
    args = parser.parse_args()
    cache_dir = Path(args.cache_dir)
    cache_diffs_path = cache_dir / "merge_diffs"
    cache_diffs_path.mkdir(parents=True, exist_ok=True)

    results_csv = pd.read_csv(args.results_csv, index_col="idx")

    print("merge_differ: Constructing Inputs")
    arguments = []
    for _, merge_data in tqdm(results_csv.iterrows(), total=len(results_csv)):
        repo_name = merge_data["repository"]

        compute = False
        for merge_tool1 in MERGE_TOOL:
            if merge_data[merge_tool1.name] not in (
                TEST_STATE.Tests_passed.name,
                TEST_STATE.Tests_failed.name,
            ):
                continue
            for merge_tool2 in MERGE_TOOL:
                if merge_data[merge_tool2.name] not in (
                    TEST_STATE.Tests_passed.name,
                    TEST_STATE.Tests_failed.name,
                ):
                    continue
                if (
                    merge_data[merge_tool1.name + "_merge_fingerprint"]
                    == merge_data[merge_tool2.name + "_merge_fingerprint"]
                ):
                    continue
                file_name = cache_diffs_path / diff_file_name(
                    merge_data[merge_tool1.name + "_merge_fingerprint"],
                    merge_data[merge_tool2.name + "_merge_fingerprint"],
                )
                if not file_name.exists():
                    compute = True
        if compute:
            arguments.append((merge_data, cache_dir))

    # Shuffle input to reduce cache contention
    random.seed(42)
    random.shuffle(arguments)

    print("merge_differ: Finished Constructing Inputs")
    print("merge_differ: Number of tested merges:", len(arguments))

    print("merge_differ: Started Diffing")
    cpu_count = os.cpu_count() or 1
    processes_used = int(cpu_count * 0.7) if cpu_count > 3 else cpu_count
    with multiprocessing.Pool(processes=processes_used) as pool:
        result = list(tqdm(pool.imap(merge_differ, arguments), total=len(arguments)))
    print("merge_differ: Finished Diffing")
