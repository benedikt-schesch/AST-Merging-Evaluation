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
from tqdm import tqdm
import pandas as pd
from repo import Repository, MERGE_TOOL


def main():  # pylint: disable=too-many-locals,too-many-statements
    """Main function"""
    print("merge_timer: Start")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_head_passes_csv", type=Path)
    parser.add_argument("--merges", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--n_sampled_timing", type=int)
    args = parser.parse_args()
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    repos = pd.read_csv(args.repos_head_passes_csv, index_col="idx")

    print("merge_timer: Started collecting merges to test")

    for _, repository_data in tqdm(repos.iterrows(), total=len(repos)):
        repo_slug = repository_data["repository"]
        merges = pd.read_csv(args.merges / f"{repo_slug}.csv")
        if len(merges) > args.n_sampled_timing:
            merges = merges.sample(n=args.n_sampled_timing, random_state=42)

        for idx, merge_data in tqdm(merges.iterrows()):
            for merge_tool in MERGE_TOOL:
                left_hash, right_hash = (
                    merge_data["left"],
                    merge_data["right"],
                )
                repo = Repository(
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
                    timeout=0,
                    use_cache=False,
                )
                merges.at[idx, f"{merge_tool.name}_merge_runtime"] = run_time
        out_file = args.output_dir / f"{repo_slug}.csv"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        merges.to_csv(out_file, index=False)
    print("merge_timer: Done")


if __name__ == "__main__":
    main()
