#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests the HEAD commits of multiple repos and considers them as valid if the test passes.

usage: python3 test_repo_heads.py --repos_csv_with_hashes <repos_csv_with_hashes.csv>
                                 --output_path <repos_head_passes.csv>
                                 --cache_dir <cache_dir>

Input: a csv of repos.  It must contain a header, one of whose columns is "repository".
That column contains "ORGANIZATION/REPO" for a GitHub repository. The csv must also
contain a column "head hash" which contains a commit hash that will be tested.
Cache_dir is the directory where the cache will be stored.
Output: the rows of the input for which the commit at head hash passes tests.
"""

import multiprocessing
import os
import argparse
import sys
from pathlib import Path
import shutil
from typing import Tuple
from repo import Repository, TEST_STATE
from variables import TIMEOUT_TESTING_PARENT
import pandas as pd
from loguru import logger
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TextColumn,
)

logger.add(sys.stderr, colorize=True, backtrace=True, diagnose=True)
logger.add("run.log", colorize=False, backtrace=True, diagnose=True)


def num_processes(percentage: float = 0.7) -> int:
    """Compute the number of CPUs to be used
    Args:
        percentage (float, optional): Percentage of CPUs to be used. Defaults to 0.7.
    Returns:
        int: the number of CPUs to be used.
    """
    cpu_count = os.cpu_count() or 1
    processes_used = int(percentage * cpu_count) if cpu_count > 3 else cpu_count
    return processes_used


def head_passes_tests(args: Tuple[pd.Series, Path]) -> pd.Series:
    """Runs tests on the head of the main branch.
    Args:
        args (Tuple[pd.Series,Path]): A tuple containing the repository info and the cache path.
    Returns:
        TEST_STATE: The result of the test.
    """
    repo_info, cache = args
    logger.info(f"head_passes_tests: Started {repo_info['repository']}")
    repo_slug = repo_info["repository"]
    if "/" not in repo_slug:
        repo_info["head test result"] = "Wrong format"
        logger.error(f"head_passes_tests: Wrong format {repo_info['repository']}")
        raise ValueError(f"Wrong format {repo_info['repository']}")

    if len(repo_info["head hash"]) != 40:
        repo_info["head test result"] = "No valid head hash"
        logger.error(f"head_passes_tests: No valid head hash {repo_info['repository']}")
        raise ValueError(f"No valid head hash {repo_info['repository']}")

    # Load repo
    try:
        repo = Repository(
            "HEAD",
            repo_slug,
            cache_directory=cache,
            workdir_id=repo_slug + "/head-" + repo_info["repository"],
            lazy_clone=True,
        )
    except Exception as e:
        repo_info["head test result"] = TEST_STATE.Git_checkout_failed.name
        repo_info["head tree fingerprint"] = None
        logger.success(
            f"head_passes_tests: Git checkout failed {repo_info['repository']} {e}"
        )
        return repo_info

    # Test repo
    test_state, _, repo_info["head tree fingerprint"] = repo.checkout_and_test(
        repo_info["head hash"], timeout=TIMEOUT_TESTING_PARENT, n_tests=3
    )
    if test_state != TEST_STATE.Tests_passed:
        shutil.rmtree(repo.repo_path, ignore_errors=True)

    repo_info["head test result"] = test_state.name

    logger.success(
        f"head_passes_tests: Finished {repo_info['repository']} {test_state}"
    )
    return repo_info


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_csv_with_hashes", type=Path)
    parser.add_argument("--output_path", type=Path)
    parser.add_argument("--cache_dir", type=Path, default="cache/")
    arguments = parser.parse_args()

    Path(arguments.cache_dir).mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(arguments.repos_csv_with_hashes, index_col="idx")

    logger.info("test_repo_heads: Started Testing")
    head_passes_tests_arguments = [(v, arguments.cache_dir) for _, v in df.iterrows()]
    with multiprocessing.Pool(processes=num_processes()) as pool:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task(
                "Testing repos...", total=len(head_passes_tests_arguments)
            )
            head_passes_tests_results = []
            for result in pool.imap(head_passes_tests, head_passes_tests_arguments):
                head_passes_tests_results.append(result)
                progress.update(task, advance=1)
    logger.info("test_repo_heads: Finished Testing")

    logger.info("test_repo_heads: Started Building Output")
    df = pd.DataFrame(head_passes_tests_results)
    filtered_df = df[df["head test result"] == TEST_STATE.Tests_passed.name]
    logger.info("test_repo_heads: Finished Building Output")

    logger.success(
        "test_repo_heads: Number of repos whose head passes tests:"
        + str(len(filtered_df))
        + "out of"
        + str(len(df))
    )
    if len(filtered_df) == 0:
        raise Exception("No repos found whose head passes tests")
    filtered_df.to_csv(arguments.output_path, index_label="idx")
    df.to_csv(
        arguments.output_path.parent / "all_repos_head_test_results.csv",
        index_label="idx",
    )
    logger.success("test_repo_heads: Done")
