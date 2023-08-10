#!/usr/bin/env python3
"""Filter the merges that will be analyzed.
usage: python3 merge_tester.py --valid_repos_csv <path_to_valid_repos.csv>
                                --merges_path <path_to_merges>
                                --output_dir <output_dir>
                                --cache_dir <cache_dir>
This script filters the merges that will be analyzed.
A merge is analyzed if it is not trivial, if it is not a merge of two initial commits,
and if a merge has at least two merge results that disagree (except if both fail)
on the merge result.
"""

import os
import multiprocessing
import argparse
from pathlib import Path
from functools import partialmethod
import numpy as np
from typing import Tuple
import pandas as pd
from repo import Repository, MERGE_TOOL, MERGE_STATE
from tqdm import tqdm
import random

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore

TIMEOUT_MERGING = 60 * 30  # 30 minutes
TIMEOUT_TESTING = 60 * 30  # 30 minutes
N_RESTARTS = 3


def merge_tester(args: Tuple[str, pd.Series, Path]) -> dict:
    """
    Merges two branches and returns the result.
    Args:
        args (Tuple[pd.Series,Path]): A tuple containing the
                merge data, the merge tool and the cache path.
    Returns:
        dict: A dictionary containing the merge result.
    """
    repo_name, merge_data, cache_prefix = args

    result = {}
    for merge_tool in MERGE_TOOL:
        repo = Repository(repo_name, cache_prefix=cache_prefix)
        (
            merge_status,
            merge_fingerprint,
            left_fingreprint,
            right_fingerprint,
            _,
            _,
        ) = repo.merge(
            tool=merge_tool,
            left_commit=merge_data["left"],
            right_commit=merge_data["right"],
            timeout=TIMEOUT_MERGING,
        )
        assert left_fingreprint == merge_data["left_tree_fingerprint"]
        assert right_fingerprint == merge_data["right_tree_fingerprint"]
        assert merge_fingerprint == merge_data[merge_tool.name + "_merge_fingerprint"]
        if merge_status == MERGE_STATE.Merge_success:
            test_result = repo.test(TIMEOUT_TESTING,N_RESTARTS)
            result[merge_tool.name] = test_result.name
        else:
            result[merge_tool.name] = merge_status.name
        del repo
    return result


if __name__ == "__main__":
    print("merge_tester: Start")
    parser = argparse.ArgumentParser()
    parser.add_argument("--valid_repos_csv", type=str)
    parser.add_argument("--merges_path", type=str)
    parser.add_argument("--output_dir", type=str)
    parser.add_argument("--cache_dir", type=str, default="cache/")
    args = parser.parse_args()
    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    repos = pd.read_csv(args.valid_repos_csv, index_col="idx")

    print("merge_tester: Constructing Inputs")
    arguments = []
    for _, repository_data in tqdm(repos.iterrows(), total=len(repos)):
        merges_repo = []
        repo_name = repository_data["repository"]
        merge_list_file = Path(
            os.path.join(args.merges_path, repo_name.split("/")[1] + ".csv")
        )
        output_file = Path(
            os.path.join(args.output_dir, repo_name.split("/")[1] + ".csv")
        )
        if not merge_list_file.exists():
            raise Exception(
                "merge_tester: Skipping",
                repo_name,
                "because it does not have a list of merge. Missing file: ",
                merge_list_file,
            )

        if output_file.exists():
            print(
                "merge_tester: Skipping", repo_name, "because it is already computed."
            )
            continue
        try:
            merges = pd.read_csv(merge_list_file,header=0)
        except pd.errors.EmptyDataError:
            print("merge_tester: Skipping", repo_name, "because it is empty.")
            continue
        merges = merges[merges["analyze"]]
        arguments += [
            (repo_name, merge_data, Path(args.cache_dir))
            for _, merge_data in merges.iterrows()
        ]

    # Shuffle input to reduce cache contention
    random.seed(42)
    random.shuffle(arguments)

    print("merge_tester: Finished Constructing Inputs")
    print("merge_tester: Number of tested merges:", len(arguments))

    print("merge_tester: Started Testing")
    cpu_count = os.cpu_count() or 1
    processes_used = int(cpu_count * 0.7) if cpu_count > 3 else cpu_count
    with multiprocessing.Pool(processes=processes_used) as pool:
        result = list(tqdm(pool.imap(merge_tester, arguments), total=len(arguments)))
    print("merge_tester: Finished Testing")

    results = {repo_name: [] for repo_name in repos["repository"]}
    print("merge_tester: Constructing Output")

    n_merges = 0
    for i in tqdm(range(len(arguments))):
        repo_name = arguments[i][0]
        merge_data = arguments[i][1]
        merge_results = result[i]

        for merge_tool in MERGE_TOOL:
           merge_data[merge_tool.name] = merge_results[merge_tool.name]

        results[repo_name].append(merge_data)

    n_total_merges = 0
    for repo_name in results:
        output_file = Path(
            os.path.join(args.output_dir, repo_name.split("/")[1] + ".csv")
        )
        if output_file.exists():
            n_total_merges += len(pd.read_csv(output_file,header=0))
            continue
        df = pd.DataFrame(results[repo_name])
        df.to_csv(output_file)
        n_total_merges += len(df)


    print("merge_tester: Number of newly tested merges:", n_merges)
    print("merge_tester: Number of total tested merges:", n_total_merges)
    print("merge_tester: Finished Constructing Output")
    print("merge_tester: Done")
