#!/usr/bin/env python3
"""Removes the merges such that all merge tools have identical output.
usage: python3 merge_tools_comparator.py --repos_head_passes_csv <path_to_repos_head_passes.csv>
                                --merges_path <path_to_merges>
                                --output_dir <output_dir>
                                --cache_dir <cache_dir>
This script flags merges that have different results for different merge tools.
The output is written in output_dir and consists of the same files as the input
files, but with an additional column that indicates whether the merge tools
differ.
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
from cache_utils import set_in_cache, lookup_in_cache, slug_repo_name
from write_head_hashes import num_processes
from variables import TIMEOUT_MERGING, N_REPETITIONS

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore


def is_merge_success(merge_state: str) -> bool:
    """Returns true if the merge state indicates success."""
    return merge_state == MERGE_STATE.Merge_success.name


def merger(  # pylint: disable=too-many-locals
    args: Tuple[str, pd.Series, Path]
) -> dict:
    """
    Merges two branches and returns the result.
    Args:
        args (Tuple[str,pd.Series,Path]): A tuple containing the repo slug,
                the merge data, and the cache path.
    Returns:
        dict: A dictionary containing the merge result.
    """
    repo_slug, merge_data, cache_directory = args

    cache_key = merge_data["left"] + "_" + merge_data["right"]
    merge_cache_directory = cache_directory / "merge_results"

    result = lookup_in_cache(cache_key, repo_slug, merge_cache_directory, True)
    if result is not None and isinstance(result, dict):
        return result

    cache_data = {}
    for merge_tool in MERGE_TOOL:
        print(
            "merge_tools_comparator: Merging",
            repo_slug,
            merge_data["left"],
            merge_data["right"],
            merge_tool.name,
        )
        cache_data[merge_tool.name] = {"results": [], "run_time": []}
        log_file: Path = (
            cache_directory
            / "merge_logs"
            / slug_repo_name(repo_slug)
            / merge_data["left"]
            / merge_data["right"]
            / (merge_tool.name + f".log")
        )
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.unlink(missing_ok=True)

        for i in range(N_REPETITIONS):
            repo = Repository(repo_slug, cache_directory=cache_directory)
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
            if i == 0:  # Only write the log file once.
                with open(log_file, "w") as f:
                    f.write(explanation)

            cache_data[merge_tool.name]["results"].append(merge_status.name)
            cache_data[merge_tool.name]["log_file"] = str(log_file)
            cache_data[merge_tool.name]["run_time"].append(run_time)
            if "merge_fingerprint" not in cache_data[merge_tool.name]:
                cache_data[merge_tool.name]["merge_fingerprint"] = merge_fingerprint
                cache_data["left_tree_fingerprint"] = left_fingerprint
                cache_data["right_tree_fingerprint"] = right_fingerprint
            else:
                assert (
                    cache_data[merge_tool.name]["merge_fingerprint"]
                    == merge_fingerprint
                )
                assert cache_data["left_tree_fingerprint"] == left_fingerprint
                assert cache_data["right_tree_fingerprint"] == right_fingerprint

    set_in_cache(cache_key, cache_data, repo_slug, merge_cache_directory)
    return cache_data


def check_if_two_merges_differ(cache_data: dict) -> bool:
    """Returns true if two merge tools differ on the same merge.
    Args:
        cache_data (dict): A dictionary containing the merge data.
    Returns:
        bool: True if two merge tools differ on the same merge.
    """
    for merge_tool1 in MERGE_TOOL:
        for merge_tool2 in MERGE_TOOL:
            if is_merge_success(
                cache_data[merge_tool1.name]["results"][0]
            ) and is_merge_success(cache_data[merge_tool2.name]["results"][0]):
                return True
            if is_merge_success(
                cache_data[merge_tool1.name]["results"][0]
            ) and is_merge_success(cache_data[merge_tool2.name]["results"][0]):
                if (
                    cache_data[merge_tool1.name]["merge_fingerprint"]
                    != cache_data[merge_tool2.name]["merge_fingerprint"]
                ):
                    return True
    return False


def build_merge_arguments(args: argparse.Namespace, repo_slug: str):
    """
    Creates the arguments for the merger function.
    Args:
        args (argparse.Namespace): The arguments to the script.
        repo_slug (str): The repository slug.
    Returns:
        list: A list of arguments for the merger function.
    """
    merge_list_file = Path(
        os.path.join(args.merges_path, slug_repo_name(repo_slug) + ".csv")
    )
    output_file = Path(
        os.path.join(args.output_dir, slug_repo_name(repo_slug) + ".csv")
    )
    if not merge_list_file.exists():
        print(
            "merge_tools_comparator:",
            repo_slug,
            "does not have a list of merges. Missing file: ",
            merge_list_file,
        )
        return []

    if output_file.exists():
        print(
            "merge_tools_comparator: Skipping",
            repo_slug,
            "because it is already computed.",
        )
        return []

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
    merges["notes"].replace(np.nan, "", inplace=True)

    arguments = [
        (repo_slug, merge_data, Path(args.cache_dir))
        for _, merge_data in merges.iterrows()
    ]
    return arguments


if __name__ == "__main__":
    print("merge_tools_comparator: Start")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_head_passes_csv", type=Path)
    parser.add_argument("--merges_path", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--cache_dir", type=Path, default="cache/merges/")
    args = parser.parse_args()
    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    repos = pd.read_csv(args.repos_head_passes_csv, index_col="idx")

    print("merge_tools_comparator: Constructing Inputs")
    merger_arguments = []
    for _, repository_data in tqdm(repos.iterrows(), total=len(repos)):
        repo_slug = repository_data["repository"]
        merger_arguments += build_merge_arguments(args, repo_slug)

    # Shuffle input to reduce cache contention
    random.seed(42)
    random.shuffle(merger_arguments)

    print("merge_tools_comparator: Finished Constructing Inputs")
    # New merges are merges whose analysis does not appear in the output folder.
    print("merge_tools_comparator: Number of new merges:", len(merger_arguments))

    print("merge_tools_comparator: Started Merging")
    with multiprocessing.Pool(processes=num_processes()) as pool:
        merger_results = list(
            tqdm(pool.imap(merger, merger_arguments), total=len(merger_arguments))
        )
    print("merge_tools_comparator: Finished Merging")

    repo_result = {repo_slug: [] for repo_slug in repos["repository"]}
    print("merge_tools_comparator: Constructing Output")
    n_new_compared = 0
    for i in tqdm(range(len(merger_arguments))):
        repo_slug = merger_arguments[i][0]
        merge_data = merger_arguments[i][1]
        cache_data = merger_results[i]
        two_merge_tools_differ = check_if_two_merges_differ(cache_data)

        merge_data["two merge tools differ"] = two_merge_tools_differ
        merge_data["left_tree_fingerprint"] = cache_data["left_tree_fingerprint"]
        merge_data["right_tree_fingerprint"] = cache_data["right_tree_fingerprint"]

        # Ignore merges that could not be checked out.
        if (
            merge_data["left_tree_fingerprint"] is None
            or merge_data["right_tree_fingerprint"] is None
        ):
            continue

        for merge_tool in MERGE_TOOL:
            merge_data[merge_tool.name] = cache_data[merge_tool.name]["results"][0]
            merge_data[merge_tool.name + "_run_time"] = np.median(
                cache_data[merge_tool.name]["run_time"]
            )
            merge_data[merge_tool.name + "_merge_fingerprint"] = cache_data[
                merge_tool.name
            ]["merge_fingerprint"]
        repo_result[repo_slug].append(merge_data)
        n_new_compared += 1

    n_total_compared = 0
    for repo_slug in repo_result:
        output_file = Path(
            os.path.join(args.output_dir, slug_repo_name(repo_slug) + ".csv")
        )
        if output_file.exists():
            try:
                n_total_compared += len(pd.read_csv(output_file, header=0))
            except pd.errors.EmptyDataError:
                print(
                    "merge_tools_comparator: Skipping",
                    repo_slug,
                    "because it does not contain any merges.",
                )
            continue
        df = pd.DataFrame(repo_result[repo_slug])
        df.sort_index(inplace=True)
        df.to_csv(output_file, index_label="idx")
        n_total_compared += len(df)

    # This is the number of merges whose "two merge tools differ" bit has been set (to true or
    # false).
    print(
        "merge_tools_comparator: Number of merge tool outputs that have been newly compared:",
        n_new_compared,
    )
    # This is the number of merges whose "two merge tools differ" bit has been to true.
    print(
        "merge_tools_comparator: Total number of merge tool outputs that have been compared:",
        n_total_compared,
    )
    print("merge_tools_comparator: Finished Constructing Output")
    print("merge_tools_comparator: Done")
