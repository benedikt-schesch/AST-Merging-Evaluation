#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze the merges i.e. check if the parents pass tests and statistics between merges.
usage: python3 merge_analyzer.py --repos_head_passes_csv <path_to_repos_head_passes.csv>
                                --merges_path <path_to_merges>
                                --output_dir <output_dir>
                                --cache_dir <cache_dir>
This script analyzes the merges i.e. it checks if the parents pass tests and it
computes statistics between merges.
The output is written in output_dir and consists of the same merges as the input
but with the test results and statistics.
"""

import os
import multiprocessing
import argparse
from pathlib import Path
from typing import Tuple, Dict, Union, Any
import random
import numpy as np
import pandas as pd
from repo import Repository, TEST_STATE
from cache_utils import set_in_cache, lookup_in_cache
from test_repo_heads import num_processes
from variables import TIMEOUT_TESTING_PARENT, N_TESTS
import matplotlib.pyplot as plt
from loguru import logger
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TextColumn,
)


def is_test_passed(test_state: str) -> bool:
    """Returns true if the test state indicates passed tests."""
    return test_state == TEST_STATE.Tests_passed.name


def get_diff_files(
    repo: Repository, left_sha: str, right_sha: str, diff_log_file: Union[None, Path]
) -> set:
    """
    Computes the diff between two branches using git diff.
    Args:
        repo (Repository): The repository object.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
    Returns:
        set: A set containing the diff result.
    """
    # Using git diff to compare the two SHAs
    command = f"git diff --name-only {left_sha} {right_sha}"
    stdout, stderr = repo.run_command(command)
    if diff_log_file:
        diff_log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(diff_log_file, "w", encoding="utf-8") as f:
            f.write(command)
            f.write("\n stdout: \n")
            f.write(stdout)
            f.write("\n stderr: \n")
            f.write(stderr)
    return set(stdout.split("\n")) if stdout else set()


def diff_merge_analyzer(
    repo_slug: str,
    left_sha: str,
    right_sha: str,
    cache_dir: Path,
) -> Dict[str, Any]:
    """
    Computes the diff between two branches using git diff.
    Args:
        repo (Repository): The repository object.
        repo_slug (str): The repository slug.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
        cache_dir (Path): The path to the cache directory.
    Returns:
        dict: A dictionary containing the diff result.
    """
    cache_key = str(left_sha) + "_" + str(right_sha)

    diff_cache_dir = cache_dir / "diff_analyzer"
    cache_data = lookup_in_cache(cache_key, repo_slug, diff_cache_dir, True)  # type: ignore

    if cache_data is not None and isinstance(cache_data, dict):
        return cache_data

    repo = Repository(
        repo_slug,
        cache_directory=cache_dir,
        workdir_id=repo_slug + "/diff-" + left_sha + "-" + right_sha,
        lazy_clone=False,
    )

    cache_data: Dict[str, Union[None, bool, str, Dict[str, str]]] = {
        "diff contains java file": None,
    }

    try:
        # Get the base sha
        command = f"git merge-base {left_sha} {right_sha}"
        base_sha = repo.run_command(command)[0].strip()

        # Using git diff to compare the two SHAs
        # Store the diff

        cache_data["diff_logs"] = {
            "left_right": str(
                diff_cache_dir / "logs" / repo_slug / (cache_key + "_left_right.log")
            ),
            "base_right": str(
                diff_cache_dir / "logs" / repo_slug / (cache_key + "_base_right.log")
            ),
            "base_left": str(
                diff_cache_dir / "logs" / repo_slug / (cache_key + "_base_left.log")
            ),
        }
        left_right_files = get_diff_files(
            repo, left_sha, right_sha, Path(cache_data["diff_logs"]["left_right"])
        )
        base_right_files = get_diff_files(
            repo, base_sha, right_sha, Path(cache_data["diff_logs"]["base_right"])
        )
        base_left_files = get_diff_files(
            repo, base_sha, left_sha, Path(cache_data["diff_logs"]["base_left"])
        )
    except RuntimeError as e:
        logger.error(
            "merge_analyzer: Error while computing diff "
            + f"for {repo_slug} {left_sha} {right_sha}: {e}"
        )
        cache_data["explanation"] = str(e)
        set_in_cache(cache_key, cache_data, repo_slug, diff_cache_dir)
        return cache_data

    # Check that at least one java file is contained in all 3 diffs
    common_files = left_right_files & base_right_files & base_left_files
    cache_data["diff contains java file"] = any(
        file.endswith(".java") for file in common_files
    )

    set_in_cache(cache_key, cache_data, repo_slug, diff_cache_dir)
    return cache_data


def merge_analyzer(
    args: Tuple[str, pd.Series, Path],
) -> pd.Series:
    """
    Merges two branches and returns the result.
    Args:
        args (Tuple[str,pd.Series,Path]): A tuple containing the repo slug,
                the merge data (which is side-effected), and the cache path.
    Returns:
        dict: A dictionary containing the merge result.
    """
    repo_slug, merge_data, cache_directory = args

    left_sha = merge_data["left"]
    right_sha = merge_data["right"]

    logger.info(f"merge_analyzer: Analyzing {repo_slug} {left_sha} {right_sha}")

    # Compute diff size in lines between left and right
    cache_data = diff_merge_analyzer(repo_slug, left_sha, right_sha, cache_directory)

    if cache_data["diff contains java file"] in (False, None):
        merge_data["test merge"] = False
        merge_data["diff contains java file"] = False
        logger.info(f"merge_analyzer: Analyzed {repo_slug} {left_sha} {right_sha}")
        return merge_data

    # Checkout left parent
    repo_left = Repository(
        repo_slug,
        cache_directory=cache_directory,
        workdir_id=repo_slug + "/left-" + left_sha + "-" + right_sha,
        lazy_clone=True,
    )

    # Checkout right parent
    repo_right = Repository(
        repo_slug,
        cache_directory=cache_directory,
        workdir_id=repo_slug + "/right-" + left_sha + "-" + right_sha,
        lazy_clone=True,
    )

    # Test left parent
    result, _, left_tree_fingerprint = repo_left.checkout_and_test(
        left_sha, TIMEOUT_TESTING_PARENT, N_TESTS
    )
    merge_data["left_tree_fingerprint"] = left_tree_fingerprint
    merge_data["left parent test result"] = result.name

    # Test right parent
    result, _, right_tree_fingerprint = repo_right.checkout_and_test(
        right_sha, TIMEOUT_TESTING_PARENT, N_TESTS
    )
    merge_data["right_tree_fingerprint"] = right_tree_fingerprint
    merge_data["right parent test result"] = result.name

    # Produce the final result
    merge_data["parents pass"] = is_test_passed(
        merge_data["left parent test result"]
    ) and is_test_passed(merge_data["right parent test result"])
    merge_data["diff contains java file"] = cache_data["diff contains java file"]
    merge_data["test merge"] = (
        merge_data["parents pass"] and merge_data["diff contains java file"] is True
    )

    logger.info(f"merge_analyzer: Analyzed {repo_slug} {left_sha} {right_sha}")

    return merge_data


def build_merge_analyzer_arguments(args: argparse.Namespace, repo_slug: str):
    """
    Creates the arguments for the merger function.
    Args:
        args (argparse.Namespace): The arguments to the script.
        repo_slug (str): The repository slug.
    Returns:
        list: A list of arguments for the merger function.
    """
    merge_list_file = Path(os.path.join(args.merges_path, repo_slug + ".csv"))
    if not merge_list_file.exists():
        raise Exception(
            "merge_analyzer: The repository does not have a list of merges.",
            repo_slug,
            merge_list_file,
        )

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
    merges["left"] = merges["left"].astype(str)
    merges["right"] = merges["right"].astype(str)
    merges["notes"].replace(np.nan, "", inplace=True)

    arguments = [
        (repo_slug, merge_data, Path(args.cache_dir))
        for _, merge_data in merges.iterrows()
    ]
    return arguments


# Plotting function using matplotlib
def plot_vertical_histogram(data, title, ax):
    """Plot a vertical histogram with the given data"""
    data = [
        data[i] for i in sorted(range(len(data)), key=lambda i: data[i], reverse=True)
    ]
    ax.bar(range(len(data)), data)
    ax.set_title(title)
    ax.set_xlabel("Repository Index")
    ax.set_ylabel("Count")


if __name__ == "__main__":
    logger.info("merge_analyzer: Start")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_head_passes_csv", type=Path)
    parser.add_argument("--merges_path", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--cache_dir", type=Path, default="cache/merge_diffs/")
    parser.add_argument("--n_sampled_merges", type=int, default=20)
    args = parser.parse_args()
    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    repos = pd.read_csv(args.repos_head_passes_csv, index_col="idx")

    logger.info("merge_analyzer: Constructing Inputs")
    merger_arguments = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("[green]Constructing Input...", total=len(repos))
        for _, repository_data in repos.iterrows():
            repo_slug = repository_data["repository"]
            merger_arguments += build_merge_analyzer_arguments(args, repo_slug)
            progress.update(task, advance=1)

    # Shuffle input to reduce cache contention
    random.seed(42)
    random.shuffle(merger_arguments)

    logger.info("merge_analyzer: Finished Constructing Inputs")
    # New merges are merges whose analysis does not appear in the output folder.
    logger.info("merge_analyzer: Number of new merges: " + str(len(merger_arguments)))

    logger.info("merge_analyzer: Started Merging")
    with multiprocessing.Pool(processes=num_processes()) as pool:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("[green]Analyzing...", total=len(merger_arguments))
            merger_results = []
            for result in pool.imap(merge_analyzer, merger_arguments):
                merger_results.append(result)
                progress.update(task, advance=1)
    logger.info("merge_analyzer: Finished Merging")

    repo_result = {repo_slug: [] for repo_slug in repos["repository"]}
    logger.info("merge_analyzer: Constructing Output")
    n_new_analyzed = 0
    n_new_candidates_to_test = 0
    n_new_passing_parents = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("[green]Processing...", total=len(merger_arguments))
        for idx, merge_data in enumerate(merger_arguments):
            repo_slug = merge_data[0]
            results_data = merger_results[idx]
            repo_result[repo_slug].append(merger_results[idx])
            n_new_analyzed += 1
            if "test merge" in results_data and results_data["test merge"]:
                n_new_candidates_to_test += 1
            if "parents pass" in results_data and results_data["parents pass"]:
                n_new_passing_parents += 1
            progress.update(task, advance=1)

    # Initialize counters
    n_total_analyzed = 0
    n_candidates_to_test = 0
    n_java_contains_diff = 0
    n_sampled_for_testing = 0

    # Data collection for histograms
    repo_data = []

    for repo_slug in repo_result:
        output_file = Path(os.path.join(args.output_dir, repo_slug + ".csv"))

        df = pd.DataFrame(repo_result[repo_slug])
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if len(df) == 0:
            df.to_csv(output_file, index_label="idx")
            continue

        # Pick randomly n_sampled_merges merges to test from the ones that are candidates
        df["sampled for testing"] = False
        testable_merges = df[df["test merge"]]
        testable_merges = testable_merges.sample(frac=1.0, random_state=42)
        sampled_merges = testable_merges[: args.n_sampled_merges]
        df.loc[sampled_merges.index, "sampled for testing"] = True

        df.sort_index(inplace=True)
        df.to_csv(output_file, index_label="idx")

        # Collect data for histograms
        repo_data.append(
            (
                repo_slug,
                len(df),
                df["test merge"].sum(),
                df["diff contains java file"].dropna().sum(),
                df["sampled for testing"].sum(),
            )
        )

        # Update global counters
        n_total_analyzed += len(df)
        n_java_contains_diff += df["diff contains java file"].dropna().sum()
        n_candidates_to_test += df["test merge"].sum()
        n_sampled_for_testing += df["sampled for testing"].sum()

    # Print summaries
    logger.success(
        "merge_analyzer: Total number of merges that have been compared: "
        + str(n_total_analyzed)
    )
    logger.success(
        "merge_analyzer: Total number of merges that have been compared and have a java diff: "
        + str(n_java_contains_diff)
    )
    logger.success(
        "merge_analyzer: Total number of merges that have been "
        "compared and are testable (Has Java Diff + Parents Pass) "
        + str(n_candidates_to_test)
    )
    logger.success(
        "merge_analyzer: Total number of merges that are testable which have been sampled "
        + str(n_sampled_for_testing)
    )
    logger.info("merge_analyzer: Finished Constructing Output")

    # Creating the plots
    repo_slugs, totals, candidates, passings, sampled = zip(*repo_data)
    fig, axs = plt.subplots(4, 1, figsize=(10, 20), tight_layout=True)
    plot_vertical_histogram(
        totals,
        f"Total Analyzed per Repository (Total: {n_total_analyzed})",
        axs[0],
    )
    plot_vertical_histogram(
        candidates,
        f"Merges which contain a Java file that has been changed (Total: {n_java_contains_diff})",
        axs[1],
    )
    plot_vertical_histogram(
        passings,
        f"Testable (Has Java Diff + Parents Pass) merge Candidates "
        f"per Repository (Total: {n_candidates_to_test})",
        axs[2],
    )
    plot_vertical_histogram(
        sampled,
        f"Sampled Merges for Testing per Repository (Total: {n_sampled_for_testing})",
        axs[3],
    )

    # Add titles and save the figure
    fig.suptitle(
        f"Merges Analysis Results (Number of Repositories: {len(repos)})", y=0.98
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])  # type: ignore

    parent_output_dir = args.output_dir.parent
    plt.savefig(parent_output_dir / "merges_analyzer_histograms.pdf")
    logger.success("merge_analyzer: Done")
