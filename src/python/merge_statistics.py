#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze merges and provide detailed statistics.

Usage: python3 merge_stats.py --repos_head_passes_csv <path_to_repos_head_passes.csv>
                              --merges_path <path_to_merges>
                              --output_csv <output_csv>
                              --cache_dir <cache_dir>

This script analyzes merges and provides detailed statistics for each merge,
including file counts, diff lines, conflicts, import changes, and non-Java code changes.
"""

import argparse
from pathlib import Path
import random
import pandas as pd
from repo import Repository
from cache_utils import set_in_cache, lookup_in_cache
from loguru import logger
from typing import Callable, List, Tuple
import multiprocessing
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


def compute_num_diff_files(repo: Repository, left_sha: str, right_sha: str) -> int:
    diff_command = f"git diff --name-only {left_sha} {right_sha}"
    output, _ = repo.run_command(diff_command)
    return len(output.splitlines())


def compute_num_diff_lines(repo: Repository, left_sha: str, right_sha: str) -> int:
    diff_command = f"git diff {left_sha} {right_sha}"
    output, _ = repo.run_command(diff_command)
    return sum(1 for line in output.splitlines() if line.startswith(("+ ", "- ")))


def compute_imports_involved(repo: Repository, left_sha: str, right_sha: str) -> bool:
    diff_command = f"git diff {left_sha} {right_sha}"
    output, _ = repo.run_command(diff_command)
    return "import " in output


def compute_non_java_involved(repo: Repository, left_sha: str, right_sha: str) -> bool:
    diff_command = f"git diff --name-only {left_sha} {right_sha}"
    output, _ = repo.run_command(diff_command)
    return any(not file.endswith(".java") for file in output.splitlines())


def get_merge_stats(
    repo: Repository,
    left_sha: str,
    right_sha: str,
    cache_dir: Path,
    stat_functions: List[Tuple[str, Callable]],
) -> dict:
    """
    Computes detailed statistics for a merge.

    Args:
        repo (Repository): The repository object.
        left_sha (str): The left (parent) SHA.
        right_sha (str): The right (merge) SHA.
        cache_dir (Path): The path to the cache directory.
        stat_functions: List of tuples containing stat name and computation function.

    Returns:
        dict: A dictionary containing the computed statistics.
    """
    cache_key = f"{left_sha}_{right_sha}"
    stats_cache_dir = cache_dir / "merge_stats"
    stats = lookup_in_cache(cache_key, repo.repo_slug, stats_cache_dir, True)

    if stats is None:
        stats = {}
    write = False

    try:
        for stat_name, stat_func in stat_functions:
            if stat_name not in stats:
                stats[stat_name] = stat_func(repo, left_sha, right_sha)
                write = True

    except Exception as e:
        logger.error(
            f"Error computing merge stats for {repo.repo_slug} {left_sha} {right_sha}: {e}"
        )
        raise e
    if write:
        set_in_cache(cache_key, stats, repo.repo_slug, stats_cache_dir)
    return stats


def analyze_merge(
    args: Tuple[str, pd.Series, Path, List[Tuple[str, Callable]]],
) -> pd.Series:
    merge_idx, merge_data, cache_directory, stat_functions = args
    repo_slug = merge_data["repository"]
    repo = Repository(
        merge_idx=merge_idx,
        repo_slug=repo_slug,
        cache_directory=cache_directory,
        workdir_id=f"{repo_slug}/stats-{merge_data['left']}-{merge_data['right']}",
        lazy_clone=False,
    )
    left_sha = merge_data["left"]
    right_sha = merge_data["right"]

    logger.info(f"Analyzing merge {merge_idx} for {repo_slug}")
    stats = get_merge_stats(repo, left_sha, right_sha, cache_directory, stat_functions)

    # Add new columns for each statistic
    for key, value in stats.items():
        merge_data[f"stat_{key}"] = value

    return merge_data


def analyze_merges(args: argparse.Namespace):
    # Load the CSV file
    merges = pd.read_csv(args.input_csv, index_col="idx")

    stat_functions = [
        ("num_files", compute_num_diff_files),
        ("num_diff_lines", compute_num_diff_lines),
        ("imports_involved", compute_imports_involved),
        ("non_java_involved", compute_non_java_involved),
    ]

    merger_arguments = []
    for merge_idx, merge_data in merges.iterrows():
        merger_arguments.append(
            (str(merge_idx), merge_data, Path(args.cache_dir), stat_functions)
        )

    # Shuffle input to reduce cache contention
    random.seed(42)
    random.shuffle(merger_arguments)

    logger.info(f"Number of merges to analyze: {len(merger_arguments)}")

    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("[green]Analyzing...", total=len(merger_arguments))
            results = []
            for result in pool.imap(analyze_merge, merger_arguments):
                results.append(result)
                progress.update(task, advance=1)

    # Combine results and save
    results_df = pd.DataFrame(results)

    # Ensure the new statistic columns are at the end
    original_columns = merges.columns.tolist()
    new_stat_columns = [col for col in results_df.columns if col.startswith("stat_")]
    final_columns = original_columns + new_stat_columns

    results_df = results_df[final_columns]

    output_file = Path(args.output_csv)
    results_df.to_csv(output_file, index_label="idx")
    logger.success(f"Saved merge stats with new columns to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_csv", type=Path, help="Path to the input CSV file")
    parser.add_argument("--output_csv", type=Path, help="Directory to save output CSV")
    parser.add_argument(
        "--cache_dir", type=Path, default="cache/", help="Directory for caching"
    )
    args = parser.parse_args()

    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)

    analyze_merges(args)
    logger.success("Merge stats analysis completed")
