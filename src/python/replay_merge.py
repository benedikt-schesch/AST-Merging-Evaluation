#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replay merges and their test results"""
import argparse
import os
from pathlib import Path
import shutil
import pandas as pd
from repo import Repository, MERGE_TOOL, TEST_STATE, MERGE_STATE
from variables import TIMEOUT_TESTING_MERGE, N_TESTS, WORKDIR_DIRECTORY
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TextColumn,
)
from loguru import logger

logger.add("replay_merge.log", mode="a")


def store_artifacts(result_df: pd.DataFrame) -> None:
    """Store artifacts in a tarball directly fro."""
    tarball_path = "replay_merge_artifacts.tar.gz"

    # Create the tarball and add files, ensuring no path modification
    with tarfile.open(tarball_path, "w:gz") as tar:
        for idx in result_df.index:
            repo_path = result_df.loc[idx, "repo path"]
            log_path = result_df.loc[idx, "merge log path"]

            # Add repository directories or files to the tarball with absolute paths
            tar.add(repo_path, arcname=repo_path)

            # Add log files to the tarball with absolute paths
            tar.add(log_path, arcname=log_path)

    logger.info("Artifacts created")


def delete_workdirs(results_df: pd.DataFrame) -> None:
    """Delete the workdirs after replaying the merges."""
    for idx in results_df.index:
        os.system("chmod -R 777 " + str(results_df.loc[idx, "repo path"]))
        shutil.rmtree(results_df.loc[idx, "repo path"])
    logger.info("Workdirs deleted")


# pylint: disable=too-many-arguments, too-many-locals
def merge_replay(
    merge_idx: str,
    repo_slug: str,
    merge_data: pd.Series,
    test_merge: bool = False,
    delete_workdir: bool = True,
    create_artifacts: bool = False,
    dont_check_fingerprints: bool = False,
) -> pd.DataFrame:
    """Replay a merge and its test results.
    Args:
        args (Tuple[str,pd.Series]): A tuple containing the repository slug,
                    the repository info, and the cache path.
    Returns:
        pd.Series: The result of the test.
    """
    result_df = pd.DataFrame()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(
            f"Replaying {repo_slug} {merge_data['left']} {merge_data['right']}",
            total=len(MERGE_TOOL),
        )
        for merge_tool in MERGE_TOOL:
            progress.update(task, advance=1)
            workdir = Path(
                f"{repo_slug}-merge-replay-{merge_tool.name}-"
                + f'{merge_data["left"]}-{merge_data["right"]}'
            )
            logger.info(
                f"merge_replay: Started {repo_slug} {merge_data['left']}"
                + f"{merge_data['right']} {merge_idx} {WORKDIR_DIRECTORY / workdir}"
            )

            if (WORKDIR_DIRECTORY / workdir).exists():
                # Ask the user if they want to delete the workdir
                logger.info(
                    f"workdir {WORKDIR_DIRECTORY / workdir} already exists for idx: {merge_idx}"
                )
                answer = input(
                    f"workdir {workdir} exists for idx: {merge_idx}. Delete it? (y/n)"
                )
                if answer == "y":
                    shutil.rmtree(WORKDIR_DIRECTORY / workdir)
                else:
                    logger.info(
                        f"workdir {WORKDIR_DIRECTORY/workdir} already exists. Skipping"
                    )
                    continue
            try:
                repo = Repository(
                    repo_slug,
                    cache_directory=Path("no_cache/"),
                    workdir_id=workdir,
                    delete_workdir=False,
                    lazy_clone=False,
                )
            except Exception as e:
                logger.error(
                    f"Git clone failed for {repo_slug} {merge_data['left']}"
                    + f"{merge_data['right']} {e}"
                )
                # Exit with 0 for CI/CD to not cause problems in case a repo is no longer available
                sys.exit(0)
            (
                merge_result,
                merge_fingerprint,
                left_fingerprint,
                right_fingerprint,
                explanation,
                _,
            ) = repo.merge(
                tool=merge_tool,
                left_commit=merge_data["left"],
                right_commit=merge_data["right"],
                timeout=TIMEOUT_TESTING_MERGE,
                use_cache=False,
            )
            root_dir = Path("replay_logs")
            log_path = root_dir / Path(
                "merges/"
                + repo_slug
                + "-"
                + merge_data["left"]
                + "-"
                + merge_data["right"]
                + "-"
                + merge_tool.name
                + ".log"
            )
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(explanation)
            assert repo.local_repo_path.exists()
            result_df.loc[
                merge_tool.name,
                ["merge result", "merge log path", "repo path", "merge fingerprint"],
            ] = [
                merge_result.name,
                log_path,
                repo.local_repo_path,
                merge_fingerprint,
            ]
            if merge_data[f"{merge_tool.name}_merge_fingerprint"] != merge_fingerprint:
                raise Exception(
                    f"fingerprints differ: after merge of {workdir} with {merge_tool}, found"
                    + f" {merge_fingerprint} but expected "
                    + f"{merge_data[f'{merge_tool.name}_merge_fingerprint']}"
                )

            if merge_result not in (
                MERGE_STATE.Merge_failed,
                MERGE_STATE.Git_checkout_failed,
                TEST_STATE.Git_checkout_failed,
            ) and (
                left_fingerprint != merge_data["left_tree_fingerprint"]
                or right_fingerprint != merge_data["right_tree_fingerprint"]
            ):
                raise Exception(
                    "merge_replay: The merge tester is not testing the correct merge.",
                    merge_result,
                    repo_slug,
                    merge_data["left"],
                    merge_data["right"],
                    left_fingerprint,
                    right_fingerprint,
                    merge_data["left_tree_fingerprint"],
                    merge_data["right_tree_fingerprint"],
                    merge_data,
                )
            if merge_result == MERGE_STATE.Merge_success:
                log_path = root_dir / Path(
                    "merge_tests/"
                    + repo_slug
                    + "-"
                    + merge_data["left"]
                    + "-"
                    + merge_data["right"]
                    + "-"
                    + merge_tool.name
                    + ".log"
                )
                if test_merge:
                    test_result, _ = repo.test(
                        timeout=TIMEOUT_TESTING_MERGE,
                        n_tests=N_TESTS,
                        use_cache=False,
                        test_log_file=log_path,
                    )
                    result_df.loc[
                        merge_tool.name,
                        ["merge test result", "merge test log path"],
                    ] = [
                        test_result.name,
                        log_path,
                    ]
                    assert merge_data[f"{merge_tool.name}"] == test_result.name
    return result_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--merges_csv",
        help="CSV file with merges that have been tested",
        type=str,
        default="results/small/result.csv",
    )
    parser.add_argument(
        "--idx",
        help="Index of the merge to replay",
        type=str,
        default="1-7",
    )
    parser.add_argument(
        "-test",
        help="Test the replay of a merge",
        action="store_true",
    )
    arguments = parser.parse_args()

    # Setup for imports
    os.system(
        "./src/scripts/merge_tools/merging/gradlew -p src/scripts/merge_tools/merging shadowJar"
    )
    os.environ["PATH"] = os.environ["PATH"] + os.getcwd() + "/src/scripts/merge_tools/:"
    os.environ["PATH"] = (
        os.environ["PATH"]
        + os.getcwd()
        + "/src/scripts/merge_tools/merging/src/main/sh/"
    )

    df = pd.read_csv(arguments.merges_csv, index_col="idx")

    repo_slug = df.loc[arguments.idx, "repository"]
    merge_data = df.loc[arguments.idx]
    repo = Repository(  # To clone the repo
        str(repo_slug),
        cache_directory=Path("no_cache/"),
        workdir_id="todelete",
    )
    for idx, row in results_df.iterrows():
        logger.info("=====================================")
        logger.info(f"Merge tool: {idx}")
        logger.info(f"Merge result: {row['merge result']}")
        logger.info(f"Merge fingerprint: {row['merge fingerprint']}")
        logger.info(f"Merge log path: {row['merge log path']}")

        if row["merge result"] == MERGE_STATE.Merge_success and args.test:
            logger.info(f"Merge test result: {row['merge test result']}")
            logger.info(f"Merge test log path: {row['merge test log path']}")

        logger.info(f"merge data test result: {merge_data[idx]}")
        logger.info(f"repo location: {row['repo path']}")

    # Create artifacts which means creating a tarball of all the relevant workdirs
    if args.create_artifacts:
        store_artifacts(results_df)
    if args.delete_workdir:
        delete_workdirs(results_df)
