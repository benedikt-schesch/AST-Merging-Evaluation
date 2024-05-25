#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test the merges and check if the parents pass tests.
usage: python3 merge_tester.py --repos_head_passes_csv <path_to_repos_head_passes.csv>
                                --merges_path <path_to_merges>
                                --output_dir <output_dir>
                                --cache_dir <cache_dir>
This script checks if the parents pass tests and if so, it tests the merges with
each merge tool.
The output is written in output_dir and consists of the same merges as the input
but with the test results.
"""

import os
import multiprocessing
import argparse
from pathlib import Path
from typing import Tuple
import random
import time
import psutil
import pandas as pd
from repo import Repository, MERGE_TOOL, TEST_STATE, MERGE_STATE
from test_repo_heads import num_processes
from variables import TIMEOUT_TESTING_MERGE, TIMEOUT_MERGING, N_TESTS
from loguru import logger
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TextColumn,
)


def merge_tester(args: Tuple[str, pd.Series, Path]) -> pd.Series:
    """Tests a merge with each merge tool.
    Args:
        args (Tuple[str,pd.Series,Path]): A tuple containing the repository slug,
                    the repository info, and the cache path.
    Returns:
        pd.Series: The result of the test.
    """
    repo_slug, merge_data, cache_directory = args
    logger.info(
        f"merge_tester: Started {repo_slug} {merge_data['left']} {merge_data['right']}"
    )
    while psutil.cpu_percent() > 90:
        logger.trace(
            "merge_tester: Waiting for CPU load to come down"
            + repo_slug
            + merge_data["left"]
            + merge_data["right"]
        )
        time.sleep(60)

    for merge_tool in MERGE_TOOL:
        repo = Repository(
            repo_slug,
            cache_directory=cache_directory,
            workdir_id=repo_slug
            + f"/merge-tester-{merge_tool.name}-"
            + f'{merge_data["left"]}-{merge_data["right"]}',
            lazy_clone=True,
        )
        (
            result,
            merge_fingerprint,
            left_fingerprint,
            right_fingerprint,
            _,
        ) = repo.merge_and_test(
            tool=merge_tool,
            left_commit=merge_data["left"],
            right_commit=merge_data["right"],
            timeout_test=TIMEOUT_TESTING_MERGE,
            timeout_merge=TIMEOUT_MERGING,
            n_tests=N_TESTS,
        )
        if result not in (
            MERGE_STATE.Merge_failed,
            MERGE_STATE.Git_checkout_failed,
            TEST_STATE.Git_checkout_failed,
        ) and (
            left_fingerprint != merge_data["left_tree_fingerprint"]
            or right_fingerprint != merge_data["right_tree_fingerprint"]
        ):
            raise Exception(
                "merge_tester: The merge tester is not testing the correct merge.",
                result,
                repo_slug,
                merge_data["left"],
                merge_data["right"],
                left_fingerprint,
                right_fingerprint,
                merge_data["left_tree_fingerprint"],
                merge_data["right_tree_fingerprint"],
                merge_data,
            )

        merge_data[merge_tool.name] = result.name
        merge_data[f"{merge_tool.name}_merge_fingerprint"] = merge_fingerprint
    logger.info(
        f"merge_tester: Finished {repo_slug} {merge_data['left']} {merge_data['right']}"
    )
    return merge_data


def build_arguments(
    args: argparse.Namespace,
    repo_slug: str,
) -> list:
    """Builds the arguments for the merge_tester function.
    Args:
        args (argparse.Namespace): The arguments of the script.
        repo_slug (str): The slug of the repository.
    Returns:
        list: The arguments for the merge_tester function.
    """
    merge_list_file = Path(os.path.join(args.merges_path, repo_slug + ".csv"))
    if not merge_list_file.exists():
        raise Exception(
            "merge_tester: The repository does not have a list of merges.",
            repo_slug,
            merge_list_file,
        )

    merges = pd.read_csv(merge_list_file, header=0, index_col="idx")
    if len(merges) == 0:
        logger.info(
            "merge_tester: Skipping"
            + repo_slug
            + "because it does not contain any merges."
        )
        return []
    merges = merges[merges["sampled for testing"]]
    return [
        (repo_slug, merge_data, Path(args.cache_dir))
        for _, merge_data in merges.iterrows()
    ]


def main():
    """Main function"""
    logger.info("merge_tester: Start")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_head_passes_csv", type=Path)
    parser.add_argument("--merges_path", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--cache_dir", type=Path, default="cache/")
    args = parser.parse_args()
    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    repos = pd.read_csv(args.repos_head_passes_csv, index_col="idx")

    logger.info("merge_tester: Started collecting merges to test")
    merge_tester_arguments = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("Collecting merges...", total=len(repos))
        for _, repository_data in repos.iterrows():
            progress.update(task, advance=1)
            repo_slug = repository_data["repository"]
            merge_tester_arguments += build_arguments(args, repo_slug)

    # Shuffle input to reduce cache contention
    random.seed(42)
    random.shuffle(merge_tester_arguments)

    logger.info("merge_tester: Finished collecting merges to test")
    logger.info(
        f"merge_tester: Number of merges to test: {len(merge_tester_arguments)}"
    )

    logger.info("merge_tester: Started Testing")
    with multiprocessing.Pool(processes=num_processes()) as pool:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task(
                "Testing merges...", total=len(merge_tester_arguments)
            )
            merge_tester_results = []
            for result in pool.imap(merge_tester, merge_tester_arguments):
                merge_tester_results.append(result)
                progress.update(task, advance=1)
    logger.info("merge_tester: Finished Testing")

    repo_result = {repo_slug: [] for repo_slug in repos["repository"]}
    logger.info("merge_tester: Started Writing Output")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(
            "Constructing output...", total=len(merge_tester_arguments)
        )
        for idx, merge_results in enumerate(merge_tester_arguments):
            progress.update(task, advance=1)
            repo_slug = merge_results[0]
            repo_result[repo_slug].append(merge_tester_results[idx])

    n_total_merges = 0
    for repo_slug in repo_result:
        output_file = Path(os.path.join(args.output_dir, repo_slug + ".csv"))
        df = pd.DataFrame(repo_result[repo_slug])
        df.sort_index(inplace=True)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_file, index_label="idx")
        n_total_merges += len(df)

    logger.success(
        "merge_tester: Number of newly tested merges: "
        + str(len(merge_tester_arguments))
    )
    logger.success(
        "merge_tester: Total number of tested merges: " + str(n_total_merges)
    )
    logger.success("merge_tester: Finished Writing Output")
    logger.success("merge_tester: Done")


if __name__ == "__main__":
    main()
