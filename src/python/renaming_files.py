# -*- coding: utf-8 -*-
"""Renames the cache files to the new naming scheme."""
from pathlib import Path
import pandas as pd
from tqdm import tqdm
from cache_utils import slug_repo_name


def old_path(repo_slug: str, cache_directory: Path):
    """Returns the old path to the cache file."""
    cache_file_name = slug_repo_name(repo_slug) + ".csv"
    cache_path = cache_directory / cache_file_name
    return cache_path


if __name__ == "__main__":
    cache_root = Path("results")
    cache_dirs = [
        cache_root / cache_dir
        for cache_dir in ["merges", "merges_analyzed", "merges_sampled", "merges_tests"]
    ]
    repos_df = pd.read_csv("input_data/repos.csv")
    for cache_directory in tqdm(cache_dirs):
        for idx, row in tqdm(repos_df.iterrows(), total=len(repos_df)):
            analyze = True
            # Check if name conflict exists
            for idx2, row2 in repos_df.iterrows():
                if idx2 == idx:
                    continue
                if slug_repo_name(row["repository"]) == slug_repo_name(
                    row2["repository"]
                ):
                    print("Name conflict exists", row["repository"], row2["repository"])
                    analyze = False
            if not analyze:
                continue

            repo_slug = row["repository"]
            old_cache_path = old_path(repo_slug, cache_directory)
            try:
                res = pd.read_csv(old_cache_path)
            except FileNotFoundError:
                continue

            new_path = cache_directory / (repo_slug + ".csv")
            new_path.parent.mkdir(parents=True, exist_ok=True)
            res.to_csv(new_path, index=False)
            old_cache_path.unlink()
