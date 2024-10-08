#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Samples n_merges for each repository.
usage: python3 merges_sampler.py --repos_head_passes_csv <path_to_repos_head_passes.csv>
                                --merges_path <path_to_merges>
                                --output_dir <output_dir>
                                --include_trivial_merges (optional)
                                --only_trivial_merges (optional)
This script samples n_merges for each repository.
If the flag --include_trivial_merges is set, then the script will also output
merges that are trivial.
If the flag --only_trivial_merges is set, then the script will only output
merges that are trivial.
"""

import os
import argparse
from pathlib import Path
import pandas as pd
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TextColumn,
)
from loguru import logger

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_head_passes_csv", type=Path)
    parser.add_argument("--merges_path", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--n_merges", type=int, default=100)
    parser.add_argument("--include_trivial_merges", action="store_true")
    parser.add_argument("--only_trivial_merges", action="store_true")
    args = parser.parse_args()

    repos = pd.read_csv(args.repos_head_passes_csv, index_col="idx")
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    missing_merges_repos = 0
    total_valid_repos = 0
    logger.info("merges_sampler: Start sampling merges...")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("Sampling merges...", total=len(repos))
        for _, repository_data in repos.iterrows():
            progress.update(task, advance=1)
            repo_slug = repository_data["repository"]
            logger.info(f"Processing {repo_slug}")
            merge_list_file = Path(os.path.join(args.merges_path, repo_slug + ".csv"))
            output_file = Path(os.path.join(args.output_dir, repo_slug + ".csv"))
            if not merge_list_file.exists():
                print(
                    f"merges_sampler: {repo_slug} does not have a list of merges."
                    f"Missing file: {merge_list_file}"
                )
                missing_merges_repos += 1
                continue

            output_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                merges = pd.read_csv(merge_list_file, header=0, index_col="idx")
            except pd.errors.EmptyDataError:
                print(
                    f"merges_sampler: Skipping {repo_slug}"
                    " because it does not contain any merges."
                )
                pd.DataFrame(columns=["idx"]).to_csv(output_file)
                continue

            merges["notes"] = merges["notes"].fillna("")
            if args.only_trivial_merges:
                merges = merges[merges["notes"].str.contains("a parent is the base")]
            elif not args.include_trivial_merges:
                merges = merges[~merges["notes"].str.contains("a parent is the base")]
            total_valid_repos += 1
            n_merges = min(merges.shape[0], args.n_merges)
            sample = merges.sample(frac=1.0, random_state=42)

            # Remove merges with the same parents
            sorted_parents = sample.apply(
                lambda x: tuple(sorted([str(x["parent_1"]), str(x["parent_2"])])),
                axis=1,
            )
            unique_indices = sorted_parents.drop_duplicates().index
            sample = sample.loc[unique_indices]
            sample = sample[:n_merges]
            sample.sort_index(inplace=True)
            logger.info(f"Sampled {n_merges} merges from {repo_slug} in {output_file}")
            sample.to_csv(output_file)

    logger.info(
        f"merges_sampler: {missing_merges_repos} files were "
        f"missing and {total_valid_repos} repos were valid."
    )
