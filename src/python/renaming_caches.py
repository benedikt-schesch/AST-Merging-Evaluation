# -*- coding: utf-8 -*-
""" Cache renaming."""
import json
from pathlib import Path
from tqdm import tqdm
import pandas as pd
from cache_utils import write_cache
from renaming_files import check_conflicts


def slug_repo_name(repo_slug: str) -> str:
    """Given a GitHub repository slug ("owner/reponame"), returns the reponame.
    Args:
        repo_slug (str): The slug of the repository, which is "owner/reponame".
    Returns:
        str: The reponame.
    """
    if len(repo_slug.split("/")) < 2:
        print(repo_slug.split("/"))
    return repo_slug.split("/")[1]


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
    conflicts = check_conflicts(repos_df)
    for cache_directory in tqdm(cache_dirs):
        for idx, repo_slug in tqdm(repos_df.loc[~conflicts, "repository"].items()):
            old_cache_path = old_path(repo_slug, cache_directory)
            if not old_cache_path.exists():
                continue

            old_cache_path = old_path(repo_slug, cache_directory)
            with open(old_cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            write_cache(cache, repo_slug, cache_directory)

        print("Removing old cache files")
        for idx, repo_slug in tqdm(repos_df.loc[:, "repository"].items()):
            old_cache_path = old_path(repo_slug, cache_directory)
            old_cache_path.unlink(missing_ok=True)
