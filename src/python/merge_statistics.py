import argparse
import subprocess
from pathlib import Path

import pandas as pd
import git
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
    return set(diff.split("\n"))


def compute_statistics(
        merge_idx: str,
        repo_slug: str,
        merge_data: pd.Series,
        results: pd.DataFrame
) -> None:
    """
    Compute statistics for a merge.
    """
    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(
            f"Computing {repo_slug} {merge_data['left']} {merge_data['right']}",
            total=9
        )

        # Create row results.
        row = {"idx": merge_idx}

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
            
        progress.update(task, advance=1)

        # Count files.
        base_left_files = get_diff_files(base, base_commit_sha, merge_data["left"])
        base_right_files = get_diff_files(base, base_commit_sha, merge_data["right"])
        row["num_files"] = len(base_left_files.union(base_right_files))
        progress.update(task, advance=1)
        
        # Count intersecting files.
        row["num_intersecting_files"] = len(base_left_files.intersection(base_right_files))
        progress.update(task, advance=1)
        
        print(row)
        


if __name__ == "__main__":
    # Create CLI arguments.
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--merges_csv",
        help="CSV file with merges that have been tested",
        type=str,
        default="results/combined/result.csv",
    )
    args = parser.parse_args()

    # Load the CSV file.
    data = pd.read_csv(args.merges_csv, index_col="idx")

    # Create result dataframe.
    results = pd.DataFrame(columns=["idx", "num_files", "num_intersecting_files", "num_hunks", "num_hunks", "num_lines",
                                    "num_intersecting_lines", "imports", "non-java-files"])

    # Get data for a merge.
    idx = "38-1"
    repo_slug = data.loc[idx, "repository"]
    merge_data = data.loc[idx]

    # Compute statistics for a merge.
    compute_statistics(idx, repo_slug, merge_data, results)
