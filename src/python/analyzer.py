""" Analysis tool. """
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
WORKDIR = ".workdir/"
# If true, the working directories in WORKDIR will be retained.
# Otherwise, it is deleted after its tests are run.
TIMEOUT_MERGE = 15 * 60  # 15 Minutes
TIMEOUT_TESTING = 45 * 60  # 45 Minutes
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


def read(path):
    """Read the first line of a file."""
    with open(path, "r") as f:
        status_name = f.readline().strip()
        return status_name


if __name__ == "__main__":
    print("merge_tester: Start")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--valid_repos_csv", type=str, default="results/valid_repos.csv"
    )
    parser.add_argument("--merges_path", type=str, default="results/merges_valid/")
    parser.add_argument("--output_file", type=str, default="none")
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
    count = 0
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
            repo_name = repository_data["repository"]
            left = merge_data["left"]
            right = merge_data["right"]
            base = merge_data["base"]
            merge = merge_data["merge"]
            cache_merge_status_prefix = os.path.join(
                args.cache_dir,
                "merge_test_results",
                "_".join([repo_name.split("/")[1], left, right, base, merge, ""]),
            )
            cache1 = cache_merge_status_prefix + "gitmerge-ort.txt"
            cache2 = cache_merge_status_prefix + "gitmerge.txt"

            result1 = read(cache1)
            result2 = read(cache2)
            if result1 == "Merge_timedout" and result2 == "Tests_passed":
                os.remove(cache1)
                count += 1
    print(count)
    # elif result1 == "Merge_failed" and result2 == "Merge_failed":
    #     print("test")

    print("merge_tester: Finished Building Function Arguments")
