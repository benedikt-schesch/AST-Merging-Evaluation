from pathlib import Path
from typing import Union, Set

from loguru import logger

from src.python.repo import Repository


def get_diff(
    repo: Repository, left_sha: str, right_sha: str, diff_log_file: Union[None, Path]
) -> str:
    """
    Computes the diff between two branches using git diff.
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


def get_diff_files_branches(repo: Repository, left_sha: str, right_sha: str) -> set:
    """
    Computes the diff between two branches using git diff.
    Args:
        repo (Repository): The repository object.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
    Returns:
        set: A set containing the diff result.
    """
    # Using git diff to compare the two SHAs
    command = f"git diff --name-only {left_sha} {right_sha}"
    stdout, _ = repo.run_command(command)
    return set(stdout.split("\n")) if stdout else set()


def get_diff_hunks(repo: Repository, left_sha: str, right_sha: str) -> int:
    """
    Compute the number of hunks that are different between two branches using git diff.
    Args:
        repo (Repository): The repository object.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
    Returns:
        int: The number of hunks that are different between the two branches.
    """
    diff, _ = repo.run_command(
        f"git diff --unified=0 {left_sha} {right_sha} | grep -c '^@@'"
    )
    return int(diff)


def get_diff_files_merge(
    repo: Repository,
    left_sha: str,
    right_sha: str,
) -> Set[str]:
    """
    Computes the diff between two branches using git diff.
    Args:
        repo (Repository): The repository object.
        merge_idx (str): The merge index, such as 42-123.
        repo_slug (str): The repository slug.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
        cache_dir (Path): The path to the cache directory.
    Returns:
        Set[str]: A set containing the diff result.
    """
    command = f"git merge-base {left_sha} {right_sha}"
    base_sha = repo.run_command(command)[0].strip()
    left_right_files = get_diff_files_branches(repo, left_sha, right_sha)
    base_right_files = get_diff_files_branches(repo, base_sha, right_sha)
    base_left_files = get_diff_files_branches(repo, base_sha, left_sha)

    # Check that at least one java file is contained in all 3 diffs
    common_files = left_right_files & base_right_files & base_left_files

    return common_files


def diff_contains_java_file(
    repo: Repository, left_sha: str, right_sha: str
) -> Union[bool, None]:
    """
    Computes the diff between two branches using git diff.
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
    Computes the diff between two branches using git diff.
    Args:
        repo (Repository): The repository object.
        left_sha (str): The left sha.
        right_sha (str): The right sha.
    Returns:
        bool: True if the diff contains a non-Java file, False otherwise.
    """
    try:
        merge_diff = get_diff_files_branches(repo, left_sha, right_sha)
    except Exception as e:
        logger.error(
            f"diff_contains_non_java_file: {left_sha} {right_sha} {repo.repo_slug} {e}"
        )
        return None
    return any(not file.endswith(".java") for file in merge_diff)


def compute_num_diff_files(
    repo: Repository, left_sha: str, right_sha: str
) -> Union[int, None]:
    try:
        diff_file = get_diff_files_branches(repo, left_sha, right_sha)
    except Exception as e:
        logger.error(
            f"compute_num_diff_files: {left_sha} {right_sha} {repo.repo_slug} {e}"
        )
        return None
    return len(diff_file)


def compute_num_diff_lines(
    repo: Repository, left_sha: str, right_sha: str
) -> Union[int, None]:
    try:
        diff = get_diff(repo, left_sha, right_sha, None)
    except Exception as e:
        logger.error(
            f"compute_num_diff_lines: {left_sha} {right_sha} {repo.repo_slug} {e}"
        )
        return None
    return sum(1 for line in diff.splitlines() if line.startswith(("+ ", "- ")))


def compute_imports_involved(
    repo: Repository, left_sha: str, right_sha: str
) -> Union[bool, None]:
    try:
        diff = get_diff(repo, left_sha, right_sha, None)
    except Exception as e:
        logger.error(
            f"compute_imports_involved: {left_sha} {right_sha} {repo.repo_slug} {e}"
        )
        return None
    return "import " in diff
