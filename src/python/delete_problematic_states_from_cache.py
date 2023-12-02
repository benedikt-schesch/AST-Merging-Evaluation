""" 
Deletes problematic states from the cache. 
A problematic state is when the merge analyzer did not have a checkout failure but the merge tester did.
"""
from argparse import ArgumentParser
from pathlib import Path
import pandas as pd
from cache_utils import load_cache, write_cache


def cleanup_cache(
    merges_to_cleanup: pd.DataFrame, cache_root: Path, delete: bool = False
) -> int:
    """Deletes problematic states from the cache.
    A problematic state is when the merge analyzer did not have a checkout failure but the merge tester did.
    Args:
        merges_to_cleanup (pd.DataFrame): The merges to cleanup.
        cache_root (Path): The path to the cache directory.
        delete (bool, optional): Whether to delete the cache entries or not. Defaults to False.
    Returns:
        int: The number of deleted cache entries.
    """
    deletetions = 0
    for _, row in merges_to_cleanup.iterrows():
        repo_slug = row["repository"]
        cache_merge_analysis = load_cache(
            repo_slug, cache_root / Path("merge_analysis")
        )
        name = row["left"] + "_" + row["right"]
        if name in cache_merge_analysis:
            cache_merge_analysis.pop(name)
            deletetions += 1
        if delete:
            write_cache(
                cache_merge_analysis, repo_slug, cache_root / Path("merge_analysis")
            )

        sha_to_remove = []
        sha_cache = load_cache(repo_slug, cache_root / Path("sha_cache_entry"))
        for key in list(sha_cache.keys()):
            if row["left"] in key or row["right"] in key:
                sha_to_remove.append(sha_cache[key]["sha"])
                sha_cache.pop(key)
                deletetions += 1
        if delete:
            write_cache(sha_cache, repo_slug, cache_root / Path("sha_cache_entry"))

        test_cache = load_cache(repo_slug, cache_root / Path("test_cache"))
        for key in list(test_cache.keys()):
            if key in sha_to_remove:
                test_cache.pop(key)
                deletetions += 1
        if delete:
            write_cache(test_cache, repo_slug, cache_root / Path("test_cache"))
    return deletetions


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--merges_to_cleanup", type=Path, default=Path("results/undesirable_states.csv")
    )
    parser.add_argument("--cache", type=Path, default=Path("cache/"))
    args = parser.parse_args()

    merges_to_cleanup = pd.read_csv(args.merges_to_cleanup, header=0, index_col="idx")
    cache_root = Path(args.cache)
    potential_deletions = cleanup_cache(merges_to_cleanup, cache_root, delete=False)

    confirm = input(f"Confirm deletion of {potential_deletions} cache entries? (y/n): ")
    if confirm.lower() != "y":
        print("Aborting...")
        exit(0)

    deletetions = cleanup_cache(merges_to_cleanup, cache_root, delete=True)
    print("Deleted", deletetions, "entries from the cache.")
