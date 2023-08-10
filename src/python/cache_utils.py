from pathlib import Path
import json
import fasteners
from typing import Union, Tuple
import multiprocessing


def get_cache_lock(repo_name: str, cache_prefix: Path):
    lock_path = cache_prefix / "locks" / (repo_name.split("/")[1] + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = fasteners.InterProcessLock(lock_path)
    return lock


def get_cache_path(repo_name: str, cache_prefix: Path) -> Path:
    cache_entry_name = repo_name.split("/")[1] + ".json"
    cache_path = cache_prefix / cache_entry_name
    return cache_path


def check_cache(
    cache_key: Union[Tuple, str], repo_name: str, cache_prefix: Path
) -> bool:
    """Checks if the repository is in the cache.
    Returns:
        bool: True if the repository is in the cache, False otherwise.
    """
    if not get_cache_path(repo_name, cache_prefix).exists():
        return False
    cache = load_cache(repo_name, cache_prefix)
    return cache_key in cache


def load_cache(repo_name: str, cache_prefix: Path) -> dict:
    """Loads the cache."""
    # print(str(get_cache_path(repo_name,cache_prefix))+multiprocessing.current_process().name+"\n")
    cache_path = get_cache_path(repo_name, cache_prefix)
    if not cache_path.exists():
        return {}
    with open(cache_path, "r") as f:
        cache_data = json.load(f)
        return cache_data


def get_cache(cache_key: Union[Tuple, str], repo_name: str, cache_prefix: Path) -> dict:
    """Loads the cache."""
    cache = load_cache(repo_name, cache_prefix)
    return cache[cache_key]


def write_cache(
    cache_key: Union[Tuple, str],
    cache_value: dict,
    repo_name: str,
    cache_prefix: Path,
    overwrite: bool = False,
) -> None:
    """Writes the cache."""
    cache_path = get_cache_path(repo_name, cache_prefix)
    cache = load_cache(repo_name, cache_prefix)
    if cache_key in cache and not overwrite:
        raise ValueError("Cache key already exists")
    cache[cache_key] = cache_value
    output = json.dumps(cache, indent=4)
    with open(cache_path, "w") as f:
        f.write(output)
        f.flush()
