#!/usr/bin/env python3
""" Contains all the functions related to the cache. """

from pathlib import Path
import json
from typing import Union, Tuple
import time
import fasteners

CACHE_BACKOFF_TIME = 2 * 60  # 2 minutes, in seconds
TIMEOUT = 90 * 60  # 90 minutes, in seconds


def get_cache_lock(repo_name: str, cache_prefix: Path):
    """Returns a lock for the repository.
    Args:
        repo_name (str): The name of the repository.
        cache_prefix (Path): The path to the cache directory.
    Returns:
        fasteners.InterProcessLock: A lock for the repository.
    """
    lock_path = cache_prefix / "locks" / (repo_name.split("/")[1] + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = fasteners.InterProcessLock(lock_path)
    return lock


def get_cache_path(repo_name: str, cache_prefix: Path) -> Path:
    """Returns the path to the cache file.
    Args:
        repo_name (str): The name of the repository.
        cache_prefix (Path): The path to the cache directory.
    Returns:
        Path: The path to the cache file.
    """
    cache_entry_name = repo_name.split("/")[1] + ".json"
    cache_path = cache_prefix / cache_entry_name
    return cache_path


def is_in_cache(
    cache_key: Union[Tuple, str], repo_name: str, cache_prefix: Path
) -> bool:
    """Checks if the key is in the cache.
    Args:
        cache_key (Union[Tuple,str]): The key to check.
        repo_name (str): The name of the repository.
        cache_prefix (Path): The path to the cache directory.
    Returns:
        bool: True if the repository is in the cache, False otherwise.
    """
    if not get_cache_path(repo_name, cache_prefix).exists():
        return False
    cache = load_cache(repo_name, cache_prefix)
    return cache_key in cache


def load_cache(repo_name: str, cache_prefix: Path) -> dict:
    """Loads the cache.
    Args:
        repo_name (str): The name of the repository.
        cache_prefix (Path): The path to the cache directory.
    Returns:
        dict: The cache.
    """
    cache_path = get_cache_path(repo_name, cache_prefix)
    if not cache_path.exists():
        return {}
    with open(cache_path, "r") as f:
        cache_data = json.load(f)
        return cache_data


def get_cache(cache_key: Union[Tuple, str], repo_name: str, cache_prefix: Path) -> dict:
    """Loads the cache and returns the value for the given key.
    Args:
        cache_key (Union[Tuple,str]): The key to check.
        repo_name (str): The name of the repository.
        cache_prefix (Path): The path to the cache directory.
    Returns:
        dict: The cache.
    """
    cache = load_cache(repo_name, cache_prefix)
    return cache[cache_key]


def write_cache(
    cache_key: Union[Tuple, str],
    cache_value: Union[str, dict, None],
    repo_name: str,
    cache_prefix: Path,
    overwrite: bool = True,
) -> None:
    """Puts an entry in the cache, then writes the cache to disk.
    Args:
        cache_key (Union[Tuple,str]): The key to check.
        cache_value (dict): The value to write.
        repo_name (str): The name of the repository.
        cache_prefix (Path): The path to the cache directory.
        overwrite (bool, optional) = True: Whether to overwrite an existing cache entry.
    """
    cache_path = get_cache_path(repo_name, cache_prefix)
    cache = load_cache(repo_name, cache_prefix)
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
    repo_name: str,
    cache_prefix: Path,
    overwrite: bool = True,
) -> None:
    """Sets the cache.
    Args:
        cache_key (Union[Tuple,str]): The key to check.
        cache_value (dict): The value to write.
        repo_name (str): The name of the repository.
        cache_prefix (Path): The path to the cache directory.
        overwrite (bool, optional) = True: Whether to overwrite the cache if it already exists.
    """
    lock = get_cache_lock(repo_name, cache_prefix)
    lock.acquire()
    cache_entry = get_cache_path(repo_name, cache_prefix)
    cache_entry.parent.mkdir(parents=True, exist_ok=True)
    write_cache(cache_key, cache_value, repo_name, cache_prefix, overwrite)
    lock.release()


def check_and_load_cache(
    cache_key: Union[Tuple, str],
    repo_name: str,
    cache_prefix: Path,
    set_run: bool = False,
) -> Union[str, dict, None]:
    """Checks if the cache is available and loads a specific entry.
    Args:
        cache_key (Union[Tuple,str]): The key to check.
        repo_name (str): The name of the repository.
        cache_prefix (Path): The path to the cache directory.
        set_run (bool, optional) = False: Whether to set the running flag to True.
    Returns:
        Union[dict,None]: The cache entry if it exists, None otherwise.
    """
    lock = get_cache_lock(repo_name, cache_prefix)
    lock.acquire()
    cache_entry = get_cache_path(repo_name, cache_prefix)
    cache_entry.parent.mkdir(parents=True, exist_ok=True)
    if is_in_cache(cache_key, repo_name, cache_prefix):
        total_time = 0
        while True:
            cache_data = get_cache(cache_key, repo_name, cache_prefix)
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
        write_cache(cache_key, None, repo_name, cache_prefix)
    lock.release()
    return None
