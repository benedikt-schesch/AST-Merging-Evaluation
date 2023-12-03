# -*- coding: utf-8 -*-
""" Cache renaming."""
import json
from pathlib import Path
from tqdm import tqdm
import pandas as pd
from cache_utils import slug_repo_name, write_cache


def old_path(repo_slug: str, cache_directory: Path):
    """Returns the old path to the cache file."""
    cache_file_name = slug_repo_name(repo_slug) + ".json"
    cache_path = cache_directory / cache_file_name
    return cache_path


if __name__ == "__main__":
    cache_root = Path("cache")
    cache_dirs = [
        cache_root / cache_dir
        for cache_dir in [
            "merge_analysis",
            "repos_head_info",
            "sha_cache_entry",
            "test_cache",
        ]
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
                with open(old_cache_path, "r", encoding="utf-8") as f:
                    cache = json.load(f)
            except FileNotFoundError:
                continue

            write_cache(cache, repo_slug, cache_directory)
            old_cache_path.unlink()
