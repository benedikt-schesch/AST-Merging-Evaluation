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

import argparse
from pathlib import Path
import pandas as pd
from repo import Repository, MERGE_TOOL
from cache_utils import lookup_in_cache, set_in_cache
import numpy as np
from loguru import logger
from variables import TIMEOUT_MERGING
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TextColumn,
)


def main():
    """Main function"""
    logger.info("merge_timer: Start")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_head_passes_csv", type=Path)
    parser.add_argument("--merges", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--n_sampled_timing", type=int)
    parser.add_argument("--cache_dir", type=Path)
    parser.add_argument("--n_timings", type=int)
    args = parser.parse_args()
    cache_dir: Path = args.cache_dir / "merge_timing_results"
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    repos = pd.read_csv(args.repos_head_passes_csv, index_col="idx")

    logger.info("merge_timer: Started collecting merges to test")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(pulse_style="blue"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("Timing merges...", total=len(repos))
        for _, repository_data in repos.iterrows():
            progress.update(task, advance=1)
            repo_slug = repository_data["repository"]
            merges = pd.read_csv(args.merges / f"{repo_slug}.csv", index_col="idx")
            merges = merges.sample(frac=1, random_state=42)
            if len(merges) > args.n_sampled_timing:
                merges = merges.iloc[: args.n_sampled_timing]
            for merge_idx, merge_data in merges.iterrows():
                for merge_tool in MERGE_TOOL:
                    left_hash, right_hash = (
                        merge_data["left"],
                        merge_data["right"],
                    )
                    cache_key = f"{left_hash}-{right_hash}-{merge_tool.name}"
                    cache_entry = lookup_in_cache(
                        cache_key, repo_slug, cache_dir, set_run=True
                    )

                    if cache_entry is not None:
                        merges.at[merge_idx, f"{merge_tool.name}_run_time"] = np.median(
                            cache_entry["run_time"]  # type: ignore
                        )
                    else:
                        logger.info(
                            f"merge_timer: Running {merge_tool.name} "
                            f"on {repo_slug} {left_hash} {right_hash}"
                        )
                        run_times = []
                        for _ in range(args.n_timings):
                            repo = Repository(
                                merge_idx,
                                repo_slug,
                                workdir_id=repo_slug
                                + f"/merge-tester-{merge_tool.name}-"
                                + f"{left_hash}-{right_hash}",
                            )
                            (
                                _,
                                _,
                                _,
                                _,
                                _,
                                run_time,
                            ) = repo.merge(
                                tool=merge_tool,
                                left_commit=left_hash,
                                right_commit=right_hash,
                                timeout=TIMEOUT_MERGING,
                                use_cache=False,
                            )
                            del repo
                            run_times.append(run_time)
                        cache_entry = {
                            "run_time": run_times,
                        }
                        set_in_cache(
                            cache_key,
                            cache_entry,
                            repo_slug,
                            cache_dir,
                            acquire_lock=False,
                        )

                    merges.at[merge_idx, f"{merge_tool.name}_run_time"] = np.median(
                        cache_entry["run_time"]  # type: ignore
                    )
            out_file = args.output_dir / f"{repo_slug}.csv"
            out_file.parent.mkdir(parents=True, exist_ok=True)
            merges.to_csv(out_file, index_label="idx")
    logger.success("merge_timer: Done")


if __name__ == "__main__":
    main()
