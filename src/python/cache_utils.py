#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contains all the functions related to the caches. The functions to interact with each
of the caches are in this file. Each cache is interacted with through the functions
of this file. The caches are all JSON files and are stored in the cache directory.
There will be 4 caches in total which are stored on disk after running the run.sh script:
1) cache/sha_cache_entry:  A cache that maps the commit hash to a sha256 hash of the repository.
2) cache/test_cache: A cache that maps a sha256 to test results.
3) cache/merge_results: A cache that maps a merge to the result
        of the merge (sha256, run time, and MERGE_STATE).
"""

from pathlib import Path
import json
from typing import Union, Tuple
import time
import fasteners
from loguru import logger

CACHE_BACKOFF_TIME = 2 * 60  # 2 minutes, in seconds
TIMEOUT = 90 * 60  # 90 minutes, in seconds


def set_in_cache(
    cache_key: Union[Tuple, str],
    cache_value: Union[str, dict, None],
    repo_slug: str,
    cache_directory: Path,
    acquire_lock: bool = True,
) -> None:
    """Puts an entry in the cache, then writes the cache to disk.
    This function is not thread-safe.
    Args:
        cache_key (Union[Tuple,str]): The key to check.
        cache_value (dict): The value to write.
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_directory (Path): The path to the cache directory.
    """
    logger.debug(
        f"set_in_cache: {cache_key} {cache_value} {repo_slug} {cache_directory}"
    )
    lock = get_cache_lock(repo_slug, cache_directory)
    if acquire_lock:
        lock.acquire()
    cache = load_cache(repo_slug, cache_directory)
    cache[cache_key] = cache_value
    write_cache(cache, repo_slug, cache_directory)
    if acquire_lock and lock is not None:
        lock.release()


def lookup_in_cache(
    cache_key: Union[Tuple, str],
    repo_slug: str,
    cache_directory: Path,
    set_run: bool = False,
) -> Union[str, dict, None]:
    """Checks if the cache is available and loads a specific entry.
    Args:
        cache_key (Union[Tuple,str]): The key to check.
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_directory (Path): The path to the cache directory.
        set_run (bool, optional) = False: Wheter to insert an empty cache entry
            if it does not exist. This is useful for preventing multiple runs from
            attempting to insert the same cache entry.
    Returns:
        Union[dict,None]: The cache entry if it exists, None otherwise.
    """
    lock = get_cache_lock(repo_slug, cache_directory)
    lock.acquire()
    cache_entry = get_cache_path(repo_slug, cache_directory)
    cache_entry.parent.mkdir(parents=True, exist_ok=True)
    if is_in_cache(cache_key, repo_slug, cache_directory):
        total_time = 0
        while True:
            cache = load_cache(repo_slug, cache_directory)
            cache_data = cache[cache_key]
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
        logger.debug(f"lookup_in_cache: Setting {cache_key} to None for {repo_slug}")
        set_in_cache(cache_key, None, repo_slug, cache_directory, acquire_lock=False)
    lock.release()
    return None


# ====================== Internal functions ======================


def get_cache_lock(repo_slug: str, cache_directory: Path):
    """Returns a lock for the cache of a repository.
    Initially the lock is unlocked; the caller must explictly
    lock and unlock the lock.
    Args:
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_directory (Path): The path to the cache directory.
    Returns:
        fasteners.InterProcessLock: A lock for the repository.
    """
    lock_path = cache_directory / "locks" / (str(repo_slug) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = fasteners.InterProcessLock(lock_path)
    return lock


def get_cache_path(repo_slug: str, cache_directory: Path) -> Path:
    """Returns the path to the cache file.
    Args:
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_directory (Path): The path to the cache directory.
    Returns:
        Path: The path to the cache file.
    """
    cache_file_name = repo_slug + ".json"
    cache_path = cache_directory / cache_file_name
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    return cache_path


def is_in_cache(
    cache_key: Union[Tuple, str], repo_slug: str, cache_directory: Path
) -> bool:
    """Checks if the key is in the cache.
    Args:
        cache_key (Union[Tuple,str]): The key to check.
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_directory (Path): The path prefix to the cache directory.
    Returns:
        bool: True if the repository is in the cache, False otherwise.
    """
    cache = load_cache(repo_slug, cache_directory)
    return cache_key in cache


def load_cache(repo_slug: str, cache_directory: Path) -> dict:
    """Loads the cache associated to the repo_slug found in the cache directory.
    Args:
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_directory (Path): The path to the cache directory.
    Returns:
        dict: The cache.
    """
    cache_path = get_cache_path(repo_slug, cache_directory)
    if not cache_path.exists():
        return {}
    with open(cache_path, "r", encoding="utf-8") as f:
        cache_data = json.load(f)
        return cache_data


def write_cache(
    cache: dict,
    repo_slug: str,
    cache_directory: Path,
) -> None:
    """Writes the cache to disk.
    Args:
        cache (dict): The cache to write.
        repo_slug (str): The slug of the repository, which is "owner/reponame".
        cache_directory (Path): The path to the cache directory.
    """
    cache_path = get_cache_path(repo_slug, cache_directory)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    output = json.dumps(cache, indent=4, sort_keys=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(output)
        f.flush()
