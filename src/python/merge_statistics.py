#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Checks some statistics between branches of a merge and outputs them to a CSV.
usage: python3 merge_statistics.py --merges_path <path_to_merges>
                                   --output_dir <output_dir>
This script computes statistics between merges via git diff and outputs them to a CSV.
It takes in one of the results CSV files and loops through each merge.

The following statistics are computed:
- Number of files in base -> left union base -> right.
- Number of intersecting files between base -> left and base -> right.
- Number of hunks between left and right.
- Number of lines between left and right.
- Number of intersecting lines between left and right.
- Whether imports are involved.
- Whether non-java files are involved.

There is another script, `merge_analyzer.py`, that computes some of the same statistics in addition to verifying tests pass.
"""

import argparse
import subprocess
from pathlib import Path
from typing import Union
from loguru import logger

import pandas as pd
from repo import Repository
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from src.python.variables import WORKDIR_DIRECTORY
from src.python.utils.diff_statistics import (
    get_diff_files_branches,
    get_diff_hunks,
    compute_num_diff_lines,
    diff_contains_non_java_file,
    compute_imports_involved,
)


def compute_statistics(
    merge_idx: str,
    repo_slug: str,
    merge_data: pd.Series,
) -> pd.DataFrame:
    """
    Compute statistics for a merge.
    Args:
        merge_idx (str): The merge index.
        repo_slug (str): The repository slug.
        merge_data (pd.Series): The merge data.
    Returns:
        pd.DataFrame: A dataframe containing the statistics.
    """
    # Create row results.
    statistics = {"idx": merge_idx}

    # Clone base, left, right branches.

    workdir = Path(
        f"{repo_slug}-merge-input-left-" + f'{merge_data["left"]}-{merge_data["right"]}'
    )
    left = Repository(
        merge_idx=merge_idx,
        repo_slug=repo_slug,
        cache_directory=Path("no_cache/"),
        workdir_id=str(workdir),
        delete_workdir=False,
        lazy_clone=False,
    )
    if not (WORKDIR_DIRECTORY / workdir).exists():
        left.checkout(merge_data["left"], use_cache=False)

    workdir = Path(
        f"{repo_slug}-merge-input-right-"
        + f'{merge_data["left"]}-{merge_data["right"]}'
    )
    right = Repository(
        merge_idx=merge_idx,
        repo_slug=repo_slug,
        cache_directory=Path("no_cache/"),
        workdir_id=str(workdir),
        delete_workdir=False,
        lazy_clone=False,
    )
    if not (WORKDIR_DIRECTORY / workdir).exists():
        right.checkout(merge_data["right"], use_cache=False)

    workdir = Path(
        f"{repo_slug}-merge-input-base-" + f'{merge_data["left"]}-{merge_data["right"]}'
    )
    base = Repository(
        merge_idx=merge_idx,
        repo_slug=repo_slug,
        cache_directory=Path("no_cache/"),
        workdir_id=str(workdir),
        delete_workdir=False,
        lazy_clone=False,
    )
    base_commit_sha = (
        subprocess.run(
            ["git", "merge-base", merge_data["left"], merge_data["right"]],
            cwd=base.local_repo_path,
            stdout=subprocess.PIPE,
        )
        .stdout.decode("utf-8")
        .strip()
    )
    if not (WORKDIR_DIRECTORY / workdir).exists():
        base.checkout(base_commit_sha, use_cache=False)

    # Count files.
    base_left_files = get_diff_files_branches(base, base_commit_sha, merge_data["left"])
    base_right_files = get_diff_files_branches(
        base, base_commit_sha, merge_data["right"]
    )
    statistics["num_files"] = len(base_left_files.union(base_right_files))

    # Count intersecting files.
    statistics["num_intersecting_files"] = len(
        base_left_files.intersection(base_right_files)
    )

    # Count hunks.
    statistics["num_hunks"] = get_diff_hunks(
        left, merge_data["left"], merge_data["right"]
    )

    # Count number of lines.
    statistics["num_lines"] = compute_num_diff_lines(
        left, merge_data["left"], merge_data["right"]
    )

    # Count number of intersecting lines.
    # TODO: Mike will implement this.
    statistics["num_intersecting_lines"] = 0

    # Check if imports are involved.
    statistics["imports"] = compute_imports_involved(
        left, merge_data["left"], merge_data["right"]
    )

    # Check if non-java files are involved.
    statistics["non_java_files"] = diff_contains_non_java_file(
        left, merge_data["left"], merge_data["right"]
    )

    # Return the row.
    return pd.DataFrame([statistics])


if __name__ == "__main__":
    # Create CLI arguments.
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--merges_csv",
        help="CSV file with merges that have been tested",
        type=str,
        default="results/combined/result.csv",
    )
    parser.add_argument(
        "--output_dir",
        help="Output directory for the statistics",
        type=str,
        default="results/combined",
    )
    args = parser.parse_args()

    # Load the CSV file.
    data = pd.read_csv(args.merges_csv, index_col="idx")

    # Create result dataframe.
    results = pd.DataFrame(
        columns=[
            "idx",
            "num_files",
            "num_intersecting_files",
            "num_hunks",
            "num_lines",
            "num_intersecting_lines",
            "imports",
            "non_java_files",
        ]
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(
            f"Computing statistics for {data.shape[0]} merges", total=data.shape[0]
        )

        # Loop through each merge.
        for idx, row in data.iterrows():
            # Get data for a merge.
            repo_slug = row["repository"]
            merge_data = row

            # Compute statistics for a merge.
            row = compute_statistics(str(idx), repo_slug, merge_data)
            results = pd.concat([results, row], ignore_index=True)

            # Update progress.
            progress.update(task, advance=1)

    # Save the results.
    results.to_csv(f"{args.output_dir}/statistics.csv", index=False)
