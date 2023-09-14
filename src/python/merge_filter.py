#!/usr/bin/env python3
"""Filter the merges that do not have at least two merge tools that 
disagree on the result of the merge.
usage: python3 merge_filter.py --valid_repos_csv <path_to_valid_repos.csv>
                                --merges_path <path_to_merges>
                                --output_dir <output_dir>
                                --cache_dir <cache_dir>
This script filters the merges that will be analyzed.
"""

import os
import multiprocessing
import argparse
from pathlib import Path
from functools import partialmethod
from typing import Tuple
import random
import numpy as np
import pandas as pd
from repo import Repository, MERGE_TOOL, MERGE_STATE
from tqdm import tqdm
from cache_utils import set_in_cache, check_and_load_cache
from write_head_hashes import compute_num_cpus_used

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore

TIMEOUT_MERGING = 60 * 15  # 15 minutes, in seconds
N_RESTARTS = 3


def is_merge_sucess(merge: str) -> bool:
    """Returns true if the merge indicates success"""
    return merge == MERGE_STATE.Merge_success.name


def merger(  # pylint: disable=too-many-locals
    args: Tuple[str, pd.Series, Path]
) -> dict:
    """
    Merges two branches and returns the result.
    Args:
        args (Tuple[pd.Series,Path]): A tuple containing the
                merge data, the merge tool and the cache path.
    Returns:
        dict: A dictionary containing the merge result.
    """
    repo_slug, merge_data, cache_prefix = args

    cache_entry = merge_data["left"] + "_" + merge_data["right"]
    merge_cache_prefix = cache_prefix / "merge_results"

    result = check_and_load_cache(cache_entry, repo_slug, merge_cache_prefix, True)
    if result is not None and isinstance(result, dict):
        return result

    cache_data = {}
    for merge_tool in MERGE_TOOL:
        print(
            "merge_filter: Merging",
            repo_slug,
            merge_data["left"],
            merge_data["right"],
            merge_tool.name,
        )
        cache_data[merge_tool.name] = {"results": [], "log_files": [], "run_time": []}
        for i in range(N_RESTARTS):
            repo = Repository(repo_slug, cache_prefix=cache_prefix)
            (
                merge_status,
                merge_fingerprint,
                left_fingerprint,
                right_fingerprint,
                explanation,
                run_time,
            ) = repo.merge(
                tool=merge_tool,
                left_commit=merge_data["left"],
                right_commit=merge_data["right"],
                timeout=TIMEOUT_MERGING,
            )
            log_file: Path = (
                cache_prefix
                / "merge_logs"
                / repo_slug.split("/")[1]
                / merge_data["left"]
                / merge_data["right"]
                / (merge_tool.name + f".log")
            )
            log_file.parent.mkdir(parents=True, exist_ok=True)
            if log_file.exists():
                log_file.unlink()
            with open(log_file, "w") as f:
                f.write(explanation)
            cache_data[merge_tool.name]["results"].append(merge_status.name)
            cache_data[merge_tool.name]["log_file"] = str(log_file)
            cache_data[merge_tool.name]["run_time"].append(run_time)
            if "merge_fingerprint" not in cache_data[merge_tool.name]:
                cache_data[merge_tool.name]["merge_fingerprint"] = merge_fingerprint
            else:
                assert (
                    cache_data[merge_tool.name]["merge_fingerprint"]
                    == merge_fingerprint
                )

            if "left_tree_fingerprint" not in cache_data:
                cache_data["left_tree_fingerprint"] = left_fingerprint
                cache_data["right_tree_fingerprint"] = right_fingerprint
            else:
                assert cache_data["left_tree_fingerprint"] == left_fingerprint
                assert cache_data["right_tree_fingerprint"] == right_fingerprint
            del repo

    set_in_cache(cache_entry, cache_data, repo_slug, cache_prefix)
    return cache_data


if __name__ == "__main__":
    print("merge_filter: Start")
    parser = argparse.ArgumentParser()
    parser.add_argument("--valid_repos_csv", type=Path)
    parser.add_argument("--merges_path", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--cache_dir", type=Path, default="cache/merges/")
    args = parser.parse_args()
    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    repos = pd.read_csv(args.valid_repos_csv, index_col="idx")

    print("merge_filter: Constructing Inputs")
    merger_arguments = []
    for _, repository_data in tqdm(repos.iterrows(), total=len(repos)):
        merges_repo = []
        repo_slug = repository_data["repository"]
        merge_list_file = Path(
            os.path.join(args.merges_path, repo_slug.split("/")[1] + ".csv")
        )
        output_file = Path(
            os.path.join(args.output_dir, repo_slug.split("/")[1] + ".csv")
        )
        if not merge_list_file.exists():
            raise Exception(
                "merge_filter.py:",
                repo_slug,
                "does not have a list of merge. Missing file: ",
                merge_list_file,
            )

        if output_file.exists():
            print(
                "merge_filter.py: Skipping",
                repo_slug,
                "because it is already computed.",
            )
            continue

        merges = pd.read_csv(
            merge_list_file,
            names=["idx", "branch_name", "merge", "left", "right", "notes"],
            dtype={
                "idx": int,
                "branch_name": str,
                "merge": str,
                "left": str,
                "right": str,
                "notes": str,
            },
            header=0,
            index_col="idx",
        )
        merger_arguments += [
            (repo_slug, merge_data, Path(args.cache_dir))
            for _, merge_data in merges.iterrows()
        ]

    # Shuffle input to reduce cache contention
    random.seed(42)
    random.shuffle(merger_arguments)

    print("merge_filter: Finished Constructing Inputs")
    # New merges are merges whose analysis does not appear in the output folder.
    print("merge_filter: Number of new merges:", len(merger_arguments))

    print("merge_filter: Started Merging")
    with multiprocessing.Pool(processes=compute_num_cpus_used()) as pool:
        merger_results = list(
            tqdm(pool.imap(merger, merger_arguments), total=len(merger_arguments))
        )
    print("merge_filter: Finished Merging")

    repo_result = {repo_slug: [] for repo_slug in repos["repository"]}
    print("merge_filter: Constructing Output")
    n_analyze = 0
    for i in tqdm(range(len(merger_arguments))):
        repo_slug = merger_arguments[i][0]
        merge_data = merger_arguments[i][1]
        cache_data = merger_results[i]
        analyze = False
        for merge_tool1 in MERGE_TOOL:
            for merge_tool2 in MERGE_TOOL:
                if is_merge_sucess(
                    cache_data[merge_tool1.name]["results"][0]
                ) and is_merge_sucess(cache_data[merge_tool2.name]["results"][0]):
                    analyze = True
                if is_merge_sucess(
                    cache_data[merge_tool1.name]["results"][0]
                ) and is_merge_sucess(cache_data[merge_tool2.name]["results"][0]):
                    if (
                        cache_data[merge_tool1.name]["merge_fingerprint"]
                        != cache_data[merge_tool2.name]["merge_fingerprint"]
                    ):
                        analyze = True
        merge_data["analyze"] = analyze
        merge_data["left_tree_fingerprint"] = cache_data["left_tree_fingerprint"]
        merge_data["right_tree_fingerprint"] = cache_data["right_tree_fingerprint"]
        for merge_tool in MERGE_TOOL:
            merge_data[merge_tool.name] = cache_data[merge_tool.name]["results"][0]
            merge_data[merge_tool.name + "_run_time"] = np.median(
                cache_data[merge_tool.name]["run_time"]
            )
            merge_data[merge_tool.name + "_merge_fingerprint"] = cache_data[
                merge_tool.name
            ]["merge_fingerprint"]

        repo_result[repo_slug].append(merge_data)
        if analyze:
            n_analyze += 1

    n_total_analyze = 0
    for repo_slug in repo_result:
        output_file = Path(
            os.path.join(args.output_dir, repo_slug.split("/")[1] + ".csv")
        )
        if output_file.exists():
            try:
                n_total_analyze += sum(pd.read_csv(output_file, header=0)["analyze"])
            except pd.errors.EmptyDataError:
                print("merge_filter.py: Skipping", repo_slug, "because it is empty.")
            continue
        df = pd.DataFrame(repo_result[repo_slug])
        df.sort_index(inplace=True)
        df.to_csv(output_file, index_label="idx")
        n_total_analyze += sum(df["analyze"])

    # This is the number of merges whose "two merge tools differ" bit has been set (to true or false).
    print(
        "merge_filter: Number of merges on which all merge tools have been newly run:",
        n_analyze,
    )
    # This is the number of merges whose "two merge tools differ" bit has been to true.
    print("merge_filter: Total number of merges to be tested:", n_total_analyze)
    print("merge_filter: Finished Constructing Output")
    print("merge_filter: Done")
