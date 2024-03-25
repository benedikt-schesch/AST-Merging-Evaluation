# -*- coding: utf-8 -*-
"""Renames the cache files to the new naming scheme."""
import os
from pathlib import Path
import pandas as pd
from tqdm import tqdm


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
    return cache_directory / (slug_repo_name(repo_slug) + ".csv")


def check_conflicts(df):
    """Checks if there are any conflicts in the repository names."""
    slugged_names = df["repository"].apply(slug_repo_name)
    return slugged_names.duplicated()


def read_csv_case_sensitive(file_path):
    """Reads a csv file with case sensitivity."""
    directory, file_name = os.path.split(file_path)
    if file_name in os.listdir(directory):
        return pd.read_csv(file_path)
    raise FileNotFoundError(f"No file found with exact case: {file_path}")


if __name__ == "__main__":
    cache_root = Path("results_greatest_hits")
    cache_dirs = [
        cache_root / d
        for d in ["merges", "merges_analyzed", "merges_sampled", "merges_tested"]
    ]

    repos_df = pd.read_csv("input_data/repos.csv")
    conflicts = check_conflicts(repos_df)

    for cache_directory in tqdm(cache_dirs):
        for idx, repo_slug in tqdm(repos_df.loc[~conflicts, "repository"].items()):
            old_cache_path = old_path(repo_slug, cache_directory)
            if not old_cache_path.exists():
                continue
            try:
                res = read_csv_case_sensitive(old_cache_path)
            except pd.errors.EmptyDataError:
                continue
            except FileNotFoundError:
                print(f"File not found: {old_cache_path}")
                continue

            new_path = cache_directory / (repo_slug + ".csv")
            new_path.parent.mkdir(parents=True, exist_ok=True)
            res.to_csv(new_path, index=False)

        print("Removing old cache files")
        for idx, repo_slug in tqdm(repos_df.loc[:, "repository"].items()):
            old_cache_path = old_path(repo_slug, cache_directory)
            old_cache_path.unlink(missing_ok=True)
