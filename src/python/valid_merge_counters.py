#!/usr/bin/env python3
""" 
This module contains functions to read and increment the number of merges
that have passing parents for each repository.
"""

from pathlib import Path
import shutil
import fasteners

VALID_MERGE_COUNTERS = Path(".valid_merges_counters/")


def read_valid_merges_counter(repo_slug: str) -> int:
    """Returns the number of merges that have passing parents for a repository.
    Args:
        repo_slug (str): The name of the repository.
    Returns:
        int: The number of merges that have passing parents for the repository.
    """
    lock_file = VALID_MERGE_COUNTERS / "lock" / (repo_slug + ".lock")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    valid_repo_count_file = VALID_MERGE_COUNTERS / repo_slug
    with fasteners.InterProcessLock(lock_file):
        valid_repo_count_file.parent.mkdir(parents=True, exist_ok=True)
        if valid_repo_count_file.is_file():
            with open(valid_repo_count_file, "r") as f:
                valid_merge_counter = int(f.read())
                return valid_merge_counter
        else:
            return 0


def increment_valid_merges(repo_slug: str) -> None:
    """Increments the number of merges that have passing parents for a repository.
    Args:
        repo_slug (str): The name of the repository.
    """
    lock_file = VALID_MERGE_COUNTERS / "lock" / (repo_slug + ".lock")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    valid_repo_count_file = VALID_MERGE_COUNTERS / repo_slug
    with fasteners.InterProcessLock(lock_file):
        valid_repo_count_file.parent.mkdir(parents=True, exist_ok=True)
        if valid_repo_count_file.is_file():
            with open(valid_repo_count_file, "r") as f:
                valid_merge_counter = int(f.read())
            with open(valid_repo_count_file, "w") as f:
                f.write(str(valid_merge_counter + 1))
        else:
            with open(valid_repo_count_file, "w") as f:
                f.write("1")


def delete_valid_merges_counters():
    """Deletes the files that contain the number of merges
    that have passing parents for each repository.
    """
    if VALID_MERGE_COUNTERS.exists():
        shutil.rmtree(VALID_MERGE_COUNTERS)
