""" Contains all the functions related to the cache. """

from pathlib import Path
import json
from typing import Union, Tuple
import fasteners


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


def check_cache(
    cache_key: Union[Tuple, str], repo_name: str, cache_prefix: Path
) -> bool:
    """Checks if the repository is in the cache.
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
    cache_value: dict,
    repo_name: str,
    cache_prefix: Path,
    overwrite: bool = False,
) -> None:
    """Writes the cache.
    Args:
        cache_key (Union[Tuple,str]): The key to check.
        cache_value (dict): The value to write.
        repo_name (str): The name of the repository.
        cache_prefix (Path): The path to the cache directory.
        overwrite (bool, optional) = False: Whether to overwrite the cache if it already exists.
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
