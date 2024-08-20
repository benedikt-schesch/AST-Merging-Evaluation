# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Union, Set

from loguru import logger

from repo import Repository


def get_diff(
    repo: Repository, left_sha: str, right_sha: str, diff_log_file: Union[None, Path]
) -> str:
    """
    Computes the git diff between two commits.
    Args:
        repo (Repository): The repository object.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
    Returns:
        str: A string containing the diff result.
    """
    command = f"git diff {left_sha} {right_sha}"
    stdout, _ = repo.run_command(command)
    return stdout


def get_diff_files(repo: Repository, left_sha: str, right_sha: str) -> set:
    """
    Computes the set of files that are different between two commits using git diff.
    Args:
        repo (Repository): The repository object.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
    Returns:
        set: A set containing the files that differ.
    """
    # Using git diff to compare the two SHAs
    command = f"git diff --name-only {left_sha} {right_sha}"
    stdout, _ = repo.run_command(command)
    return set(stdout.split("\n")) if stdout else set()


def compute_num_diff_hunks(repo: Repository, left_sha: str, right_sha: str) -> int:
    """
    Compute the number of hunks that are different between two commits using git diff.
    Args:
        repo (Repository): The repository object.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
    Returns:
        int: The number of hunks that are different between the two commits.
    """
    try:
        diff, _ = repo.run_command(
            f"git diff --unified=0 {left_sha} {right_sha} | grep -c '^@@'"
        )
    except Exception as e:
        logger.error(
            f"compute_num_diff_hunks: {left_sha} {right_sha} {repo.repo_slug} {e}"
        )
        return "Error"
    return int(diff)


def get_diff_files_merge(
    repo: Repository,
    left_sha: str,
    right_sha: str,
) -> Set[str]:
    """
    Computes the intersection of files that are different between a three-way merge using git diff.
    Args:
        repo (Repository): The repository object.
        merge_idx (str): The merge index, such as 42-123.
        repo_slug (str): The repository slug.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
        cache_dir (Path): The path to the cache directory.
    Returns:
        Set[str]: A set containing the files that differ.
    """
    command = f"git merge-base {left_sha} {right_sha}"
    base_sha = repo.run_command(command)[0].strip()
    left_right_files = get_diff_files(repo, left_sha, right_sha)
    base_right_files = get_diff_files(repo, base_sha, right_sha)
    base_left_files = get_diff_files(repo, base_sha, left_sha)

    # Check that at least one java file is contained in all 3 diffs
    common_files = left_right_files & base_right_files & base_left_files

    return common_files


def diff_contains_java_file(
    repo: Repository, left_sha: str, right_sha: str
) -> Union[bool, None]:
    """
    Computes whether the diff between two commits contains a java file.
    Args:
        repo (Repository): The repository object.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
    Returns:
        bool: True if the diff contains a java file, False otherwise.
    """
    try:
        merge_diff = get_diff_files_merge(repo, left_sha, right_sha)
    except Exception as e:
        logger.error(
            f"diff_contains_java_file: {left_sha} {right_sha} {repo.repo_slug} {e}"
        )
        return None
    return any(file.endswith(".java") for file in merge_diff)


def diff_contains_non_java_file(
    repo: Repository, left_sha: str, right_sha: str
) -> Union[bool, None]:
    """
    Computes whether the diff between two commits contains a non-Java file.
    Args:
        repo (Repository): The repository object.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
    Returns:
        bool: True if the diff contains a non-Java file, False otherwise.
    """
    try:
        merge_diff = get_diff_files(repo, left_sha, right_sha)
    except Exception as e:
        logger.error(
            f"diff_contains_non_java_file: {left_sha} {right_sha} {repo.repo_slug} {e}"
        )
        return None
    return any(not file.endswith(".java") for file in merge_diff)


def compute_num_different_files(
    repo: Repository, left_sha: str, right_sha: str
) -> Union[int, None]:
    """
    Computes the number of files that are different between two commits.
    Args:
        repo (Repository): The repository object.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
    Returns:
        int: The number of files that are different between the two commits.
    """
    try:
        diff_file = get_diff_files(repo, left_sha, right_sha)
    except Exception as e:
        logger.error(
            f"compute_num_different_files: {left_sha} {right_sha} {repo.repo_slug} {e}"
        )
        return None
    return len(diff_file)


def compute_union_of_different_files_three_way(
    repo: Repository, base_sha: str, left_sha: str, right_sha: str
) -> int:
    """
    Computes the union of files that are different between a three-way merge using git diff.
    Args:
        repo (Repository): The repository object.
        base_sha (str): The base sha.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
    Returns:
        int: The number of files that are invovled in a git diff between the two commits.
    """
    base_left_files = get_diff_files(repo, base_sha, left_sha)
    base_right_files = get_diff_files(repo, base_sha, right_sha)

    return len(base_left_files.union(base_right_files))


def compute_intersection_of_diff(
    repo: Repository, base_sha: str, left_sha: str, right_sha: str
) -> int:
    """
    Computes the intersection of files that are different between a three-way merge using git diff.
    Args:
        repo (Repository): The repository object.
        base_sha (str): The base sha.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
    Returns:
        int: The number of common files between the two commits in a git diff.
    """
    base_left_files = get_diff_files(repo, base_sha, left_sha)
    base_right_files = get_diff_files(repo, base_sha, right_sha)

    return len(base_left_files.intersection(base_right_files))


def compute_num_different_lines(
    repo: Repository, left_sha: str, right_sha: str
) -> Union[int, None]:
    """
    Computes the number of lines that are different between two commits.
    Args:
        repo (Repository): The repository object.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
    Returns:
        int: The number of lines that are different between the two commits.
    """
    try:
        diff = get_diff(repo, left_sha, right_sha, None)
    except Exception as e:
        logger.error(
            f"compute_num_different_lines: {left_sha} {right_sha} {repo.repo_slug} {e}"
        )
        return None
    return sum(
        1
        for line in diff.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++ ", "--- "))
    )


def compute_are_imports_involved(
    repo: Repository, left_sha: str, right_sha: str
) -> Union[bool, None]:
    """
    Computes whether the diff between two commits contains an import statement.
    Args:
        repo (Repository): The repository object.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
    Returns:
        bool: True if the diff contains an import statement, False otherwise.
    """
    try:
        diff = get_diff(repo, left_sha, right_sha, None)
    except Exception as e:
        logger.error(
            f"compute_imports_involved: {left_sha} {right_sha} {repo.repo_slug} {e}"
        )
        return None
    return "import " in diff
