import argparse
import subprocess
from pathlib import Path
from typing import Union
from loguru import logger

import pandas as pd
from repo import Repository
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn

from src.python.variables import WORKDIR_DIRECTORY


def get_diff_files(base_repo: Repository, base_sha: str, other_sha: str) -> set:
    """
    Compute the files that are different between two branches using git diff.
    
    :param base_repo: Repository object for the base repository.
    :param base_sha: SHA of the base commit.
    :param other_sha: SHA of the other commit.
    :return: Set of file names that are different between the two branches.
    """
    diff, _ = base_repo.run_command(f"git diff --name-only {base_sha} {other_sha}")
    return set(diff.split("\n")) if diff else set()


def get_diff_hunks(left_repo: Repository, left_sha: str, right_sha: str) -> int:
    """
    Compute the number of hunks that are different between two branches using git diff.
    
    :param left_repo: Repository object for the left repository.
    :param left_sha: SHA of the left commit.
    :param right_sha: SHA of the right commit.
    :return: Number of hunks that are different between the two branches.
    """
    diff, _ = left_repo.run_command(f"git diff --unified=0 {left_sha} {right_sha} | grep -c '^@@'")
    return int(diff)


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
        bool: True if the diff contains a non-java file, False otherwise.
    """
    try:
        merge_diff = get_diff_files(repo, left_sha, right_sha)
    except Exception as e:
        logger.error(
            f"diff_contains_non_java_file: {left_sha} {right_sha} {repo.repo_slug} {e}"
        )
        return None
    return any(not file.endswith(".java") for file in merge_diff)


def compute_statistics(
        merge_idx: str,
        repo_slug: str,
        merge_data: pd.Series,
) -> pd.DataFrame:
    """
    Compute statistics for a merge.
    """
    # Create row results.
    statistics = {"idx": merge_idx}

    # Clone base, left, right branches.

    workdir = Path(
        f"{repo_slug}-merge-input-left-"
        + f'{merge_data["left"]}-{merge_data["right"]}'
    )
    left = Repository(
        merge_idx=merge_idx,
        repo_slug=repo_slug,
        cache_directory=Path("no_cache/"),
        workdir_id=str(workdir),
        delete_workdir=False,
        lazy_clone=False,
    )
    if not (WORKDIR_DIRECTORY / workdir).exists():
        left.checkout(merge_data["left"], use_cache=False)

    workdir = Path(
        f"{repo_slug}-merge-input-right-"
        + f'{merge_data["left"]}-{merge_data["right"]}'
    )
    right = Repository(
        merge_idx=merge_idx,
        repo_slug=repo_slug,
        cache_directory=Path("no_cache/"),
        workdir_id=str(workdir),
        delete_workdir=False,
        lazy_clone=False,
    )
    if not (WORKDIR_DIRECTORY / workdir).exists():
        right.checkout(merge_data["right"], use_cache=False)

    workdir = Path(
        f"{repo_slug}-merge-input-base-"
        + f'{merge_data["left"]}-{merge_data["right"]}'
    )
    base = Repository(
        merge_idx=merge_idx,
        repo_slug=repo_slug,
        cache_directory=Path("no_cache/"),
        workdir_id=str(workdir),
        delete_workdir=False,
        lazy_clone=False,
    )
    base_commit_sha = (
        subprocess.run(
            ["git", "merge-base", merge_data["left"], merge_data["right"]],
            cwd=base.local_repo_path,
            stdout=subprocess.PIPE,
        )
        .stdout.decode("utf-8")
        .strip()
    )
    if not (WORKDIR_DIRECTORY / workdir).exists():
        base.checkout(base_commit_sha, use_cache=False)

    # Count files.
    base_left_files = get_diff_files(base, base_commit_sha, merge_data["left"])
    base_right_files = get_diff_files(base, base_commit_sha, merge_data["right"])
    statistics["num_files"] = len(base_left_files.union(base_right_files))

    # Count intersecting files.
    statistics["num_intersecting_files"] = len(base_left_files.intersection(base_right_files))

    # Count hunks.
    statistics["num_hunks"] = get_diff_hunks(left, merge_data["left"], merge_data["right"])

    # Count number of lines.
    statistics["num_lines"] = compute_num_diff_lines(left, merge_data["left"], merge_data["right"])

    # Count number of intersecting lines.
    # TODO: Mike will implement this.
    statistics["num_intersecting_lines"] = 0

    # Check if imports are involved.
    statistics["imports"] = compute_imports_involved(left, merge_data["left"], merge_data["right"])

    # Check if non-java files are involved.
    statistics["non_java_files"] = diff_contains_non_java_file(left, merge_data["left"], merge_data["right"])

    # Return the row.
    return pd.DataFrame([statistics])


if __name__ == "__main__":
    # Create CLI arguments.
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--merges_csv",
        help="CSV file with merges that have been tested",
        type=str,
        default="results/combined/result.csv",
    )
    parser.add_argument(
        "--output_dir",
        help="Output directory for the statistics",
        type=str,
        default="results/combined",
    )
    args = parser.parse_args()

    # Load the CSV file.
    data = pd.read_csv(args.merges_csv, index_col="idx")

    # Create result dataframe.
    results = pd.DataFrame(columns=["idx", "num_files", "num_intersecting_files", "num_hunks", "num_lines",
                                    "num_intersecting_lines", "imports", "non_java_files"])

    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(
            f"Computing statistics for {data.shape[0]} merges",
            total=data.shape[0]
        )
        for idx, row in data.iterrows():
            # Get data for a merge.
            repo_slug = row["repository"]
            merge_data = row

            # Compute statistics for a merge.
            row = compute_statistics(str(idx), repo_slug, merge_data)
            results = pd.concat([results, row], ignore_index=True)

            # Update progress.
            progress.update(task, advance=1)

    # Save the results.
    results.to_csv(f"{args.output_dir}/statistics.csv", index=False)
