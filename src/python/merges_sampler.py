#!/usr/bin/env python3
""" Samples n_merges for each repository.
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
from tqdm import tqdm
import numpy as np
from cache_utils import slug_repo_name

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
    for _, repository_data in tqdm(repos.iterrows(), total=len(repos)):
        repo_slug = repository_data["repository"]
        merge_list_file = Path(
            os.path.join(args.merges_path, slug_repo_name(repo_slug) + ".csv")
        )
        output_file = Path(
            os.path.join(args.output_dir, slug_repo_name(repo_slug) + ".csv")
        )
        if not merge_list_file.exists():
            print(
                "merges_sampler:",
                repo_slug,
                "does not have a list of merges. Missing file: ",
                merge_list_file,
            )
            missing_merges_repos += 1
            continue

        if output_file.exists():
            print(
                "merges_sampler: Skipping",
                repo_slug,
                "because it is already computed.",
            )
            continue
        try:
            merges = pd.read_csv(merge_list_file, header=0, index_col="idx")
        except pd.errors.EmptyDataError:
            print(
                "merges_sampler: Skipping",
                repo_slug,
                "because it does not contain any merges.",
            )
            continue

        merges["notes"].replace(np.nan, "", inplace=True)
        if args.only_trivial_merges:
            merges = merges[merges["notes"].str.contains("a parent is the base")]
        elif not args.include_trivial_merges:
            merges = merges[~merges["notes"].str.contains("a parent is the base")]
        total_valid_repos += 1
        n_merges = min(merges.shape[0], args.n_merges)
        sample = merges.sample(frac=1.0, random_state=42)
        sample = sample[:n_merges]
        sample.sort_index(inplace=True)
        sample.to_csv(output_file)

    print(
        f"merges_sampler: {missing_merges_repos} files were missing and {total_valid_repos} repos were valid.")