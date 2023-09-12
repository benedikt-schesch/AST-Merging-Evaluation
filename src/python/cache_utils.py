#!/usr/bin/env python3
""" Contains all the functions related to the caches. 
TODO: Elsewhere, the code speaks of "the cache" (example: get_cache_lock), but here it speaks of 4 caches. I'm confused about the relationship.
TODO: Are there 4 caches overall, or 4 caches per repository, or something else? Please clarify.
TODO: "after running the script": Which script?
There will be 4 caches which are stored on disk after running the script:
TODO: Is the cache directory literally named "cache"?  Where is it on disk?
TODO: Are all the caches JSON files?
1) cache/sha_cache_entry:  A cache that maps the commit hash to a sha256 hash of the repository.
2) cache/test_cache: A cache that maps a sha256 to test results.
3) cache/merge_results:A cache that maps a merge to the result 
        of the merge (sha256, runtime and MERGE_STATE)
4) cache/merge_diffs: A cache that stores the diff between merge tools.
"""

from pathlib import Path
import json
from typing import Union, Tuple
import time
import fasteners

CACHE_BACKOFF_TIME = 2 * 60  # 2 minutes, in seconds
TIMEOUT = 90 * 60  # 90 minutes, in seconds

# TODO: In this file, please place the externally-visible or exported functions
# first, and then a comment marker of some kind, and then the "private" ones.


def slug_repo_name(repo_slug: str) -> str:
    """Given a GitHub repository slug (owner/reponame), returns the reponame.
    Args:
        repo_slug (str): The slug of the repository, which is 'owner/reponame'.
    Returns:
        str: The reponame.
    """
    return repo_slug.split("/")[1]


# TODO: Throughout, please use "_directory" instead of "_prefix" in
# variable names, when the variable actually holds a directory.  I
# feel this will be clearer.
def get_cache_lock(repo_slug: str, cache_prefix: Path):
    """Returns a lock for the cache of a repository.
    Initially the lock is unlocked; the caller must explictly
    lock and unlock the lock.
    Args:
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_prefix (Path): The path to the cache directory.
    Returns:
        fasteners.InterProcessLock: A lock for the repository.
    """
    lock_path = cache_prefix / "locks" / (slug_repo_name(repo_slug) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = fasteners.InterProcessLock(lock_path)
    return lock


def get_cache_path(repo_slug: str, cache_prefix: Path) -> Path:
    """Returns the path to the cache file.
    Args:
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_prefix (Path): The path to the cache directory.
    Returns:
        Path: The path to the cache file.
    """
    cache_entry_name = slug_repo_name(repo_slug) + ".json"
    cache_path = cache_prefix / cache_entry_name
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    return cache_path


def is_in_cache(
    cache_key: Union[Tuple, str], repo_slug: str, cache_prefix: Path
) -> bool:
    """Checks if the key is in the cache.
    Args:
        cache_key (Union[Tuple,str]): The key to check.
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_prefix (Path): The path prefix to the cache directory.
    Returns:
        bool: True if the repository is in the cache, False otherwise.
    """
    cache = load_cache(repo_slug, cache_prefix)
    return cache_key in cache


def load_cache(repo_slug: str, cache_prefix: Path) -> dict:
    # TODO: "the cache": which one?  Also, does this load a cache or a cache
    # entry?  Please define those terms to help the reader.  This method returns
    # a cache, which is a dict.  `cache_lookup` returns a cache entry, which is
    # also a dict.  What are they dicts from and to?
    """Loads the cache.
    Args:
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_prefix (Path): The path to the cache directory.
    Returns:
        dict: The cache.
    """
    cache_path = get_cache_path(repo_slug, cache_prefix)
    if not cache_path.exists():
        return {}
    with open(cache_path, "r") as f:
        cache_data = json.load(f)
        return cache_data


def cache_lookup(
    cache_key: Union[Tuple, str], repo_slug: str, cache_prefix: Path
) -> dict:
    """Loads the cache and returns the value for the given key.
    Args:
        cache_key (Union[Tuple,str]): The key to check.
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_prefix (Path): The path to the cache directory.
    Returns:
        dict: The cache.
    """
    cache = load_cache(repo_slug, cache_prefix)
    return cache[cache_key]


# TODO: The distinction between write_to_cache and set_in_cache is not clear to
# me.  If it is only locking, then please give them the same name, but with one
# suffixed by "_without_lock".  Also please indicate under what circumstances
# each should be called.
def write_to_cache(
    cache_key: Union[Tuple, str],
    cache_value: Union[str, dict, None],
    repo_slug: str,
    cache_prefix: Path,
    overwrite: bool = True,
) -> None:
    """Puts an entry in the cache, then writes the cache to disk.
    This function is not thread-safe.
    Args:
        cache_key (Union[Tuple,str]): The key to check.
        cache_value (dict): The value to write.
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_prefix (Path): The path to the cache directory.
        overwrite (bool, optional) = True: Whether to overwrite an existing cache entry.
             If False, attempting to overwrite an existing cache entry throws an exception.
    """
    cache_path = get_cache_path(repo_slug, cache_prefix)
    cache = load_cache(repo_slug, cache_prefix)
    if cache_prefix != Path("cache-small/sha_cache_entry"):
        print("write_to_cache:", cache_key, cache_value, repo_slug, cache_prefix)
    if cache_key in cache and not overwrite:
        raise ValueError("Cache key already exists")
    cache[cache_key] = cache_value
    output = json.dumps(cache, indent=4)
    with open(cache_path, "w") as f:
        f.write(output)
        f.flush()


def set_in_cache(
    cache_key: Union[Tuple, str],
    cache_value: Union[str, dict, None],
    repo_slug: str,
    cache_prefix: Path,
    overwrite: bool = True,
) -> None:
    """Puts an entry in the cache, then writes the cache to disk.
    This function is thread-safe.
    Args:
        cache_key (Union[Tuple,str]): The key to check.
        cache_value (dict): The value to write.
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_prefix (Path): The path to the cache directory.
        overwrite (bool, optional) = True: Whether to overwrite the cache if it already exists.
    """
    lock = get_cache_lock(repo_slug, cache_prefix)
    lock.acquire()
    write_to_cache(cache_key, cache_value, repo_slug, cache_prefix, overwrite)
    lock.release()


# TODO: I'm not clear what is the difference between `cache_lookup` and
# `lookup_in_cache`.  Please clarify, and indicate when each should be called.
def lookup_in_cache(
    cache_key: Union[Tuple, str],
    repo_slug: str,
    cache_prefix: Path,
    set_run: bool = False,
) -> Union[str, dict, None]:
    """Checks if the cache is available and loads a specific entry.
    Args:
        cache_key (Union[Tuple,str]): The key to check.
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_prefix (Path): The path to the cache directory.
        set_run (bool, optional) = False: Wheter to insert an empty cache entry
            if it does not exist. This is useful for preventing multiple runs from
            attempting to insert the same cache entry.
    Returns:
        Union[dict,None]: The cache entry if it exists, None otherwise.
    """
    lock = get_cache_lock(repo_slug, cache_prefix)
    lock.acquire()
    cache_entry = get_cache_path(repo_slug, cache_prefix)
    cache_entry.parent.mkdir(parents=True, exist_ok=True)
    if is_in_cache(cache_key, repo_slug, cache_prefix):
        total_time = 0
        while True:
            cache_data = cache_lookup(cache_key, repo_slug, cache_prefix)
            if cache_data is not None:
                break
            lock.release()
            time.sleep(CACHE_BACKOFF_TIME)
            total_time += CACHE_BACKOFF_TIME
            if total_time > TIMEOUT:
                return None
            lock.acquire()
        lock.release()
        return cache_data
    if set_run:
        write_to_cache(cache_key, None, repo_slug, cache_prefix)
    lock.release()
    return None
