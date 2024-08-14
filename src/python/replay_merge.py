#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replay merges and their test results.
The output appears in the .workdirs/ directory.
Command-line arguments are listed just after the line:
  if __name__ == "__main__":

Typical usage:
  replay_merge.py --idx INDEX
where INDEX is, for example, 38-192 .
"""

import argparse
import git
import os
import sys
import tarfile
from pathlib import Path
import shutil
import subprocess
import pandas as pd
from repo import Repository, MERGE_TOOL, TEST_STATE, MERGE_STATE
from variables import TIMEOUT_TESTING_MERGE, N_TESTS, WORKDIR_DIRECTORY, TIMEOUT_MERGING
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
            tar.add(repo_path, arcname=repo_path)  # type: ignore

            # Add log files to the tarball with absolute paths
            tar.add(log_path, arcname=log_path)  # type: ignore

    logger.info("Artifacts created")


def delete_workdirs(results_df: pd.DataFrame) -> None:
    """Delete the workdirs after replaying the merges."""
    for idx in results_df.index:
        os.system("chmod -R 777 " + str(results_df.loc[idx, "repo path"]))
        shutil.rmtree(results_df.loc[idx, "repo path"])  # type: ignore
    logger.info("Workdirs deleted")


def merge_replay(
    merge_idx: str,
    repo_slug: str,
    merge_data: pd.Series,
    test_merge: bool = False,
    delete_workdir: bool = True,
    create_artifacts: bool = False,
    dont_check_fingerprints: bool = False,
    testing: bool = False,
) -> pd.DataFrame:
    """Replay a merge and its test results.
    Args:
        merge_idx (str): The index of the merge.
        repo_slug (str): The repository slug.
        merge_data (pd.Series): The data of the merge.
        test_merge (bool, optional): Whether to test the merge. Defaults to False.
        delete_workdir (bool, optional): Whether to delete the workdir. Defaults to True.
        create_artifacts (bool, optional): Whether to create artifacts. Defaults to False.
        dont_check_fingerprints (bool, optional): Whether to check the fingerprints.
            Defaults to False.
        testing (bool, optional): Whether to check for reproducibility. Defaults to False.
    Returns:
        pd.Series: The result of the test.
    """

    ast_merging_evaluation_repo = git.Repo(".", search_parent_directories=True)
    if ast_merging_evaluation_repo.working_tree_dir is None:
        raise Exception("Could not find the ast-merging-evaluation repository")
    plumelib_merging_dir = Path(ast_merging_evaluation_repo.working_tree_dir) / Path(
        "src/scripts/merge_tools/merging"
    )
    subprocess.run(["./gradlew", "-q", "shadowJar"], cwd=plumelib_merging_dir)

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

        # Get base, left, right, and programmer merge.

        workdir = Path(
            f"{repo_slug}-merge-input-left-"
            + f'{merge_data["left"]}-{merge_data["right"]}'
        )
        if not (WORKDIR_DIRECTORY / workdir).exists():
            repo = Repository(
                merge_idx,
                repo_slug,
                cache_directory=Path("no_cache/"),
                workdir_id=str(workdir),
                delete_workdir=True if delete_workdir else False,
                lazy_clone=False,
            )
            repo.checkout(merge_data["left"], use_cache=False)

        workdir = Path(
            f"{repo_slug}-merge-input-right-"
            + f'{merge_data["left"]}-{merge_data["right"]}'
        )
        if not (WORKDIR_DIRECTORY / workdir).exists():
            repo = Repository(
                merge_idx=merge_idx,
                repo_slug=repo_slug,
                cache_directory=Path("no_cache/"),
                workdir_id=str(workdir),
                delete_workdir=False,
                lazy_clone=False,
            )
            repo.checkout(merge_data["right"], use_cache=False)

        workdir = Path(
            f"{repo_slug}-merge-input-base-"
            + f'{merge_data["left"]}-{merge_data["right"]}'
        )
        if not (WORKDIR_DIRECTORY / workdir).exists():
            repo = Repository(
                merge_idx=merge_idx,
                repo_slug=repo_slug,
                cache_directory=Path("no_cache/"),
                workdir_id=str(workdir),
                delete_workdir=False,
                lazy_clone=False,
            )
            base_commit = (
                subprocess.run(
                    ["git", "merge-base", merge_data["left"], merge_data["right"]],
                    cwd=repo.local_repo_path,
                    stdout=subprocess.PIPE,
                )
                .stdout.decode("utf-8")
                .strip()
            )
            repo.checkout(base_commit, use_cache=False)

        workdir = Path(
            f"{repo_slug}-merge-input-programmer-"
            + f'{merge_data["left"]}-{merge_data["right"]}'
        )
        if not (WORKDIR_DIRECTORY / workdir).exists():
            repo = Repository(
                merge_idx=merge_idx,
                repo_slug=repo_slug,
                cache_directory=Path("no_cache/"),
                workdir_id=str(workdir),
                delete_workdir=False,
                lazy_clone=False,
            )
            repo.checkout(merge_data["merge"], use_cache=False)

        for merge_tool in MERGE_TOOL:
            if testing:
                if merge_tool == MERGE_TOOL.spork:
                    continue
                if merge_tool == MERGE_TOOL.intellimerge:
                    continue
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
                    f"Workdir {WORKDIR_DIRECTORY / workdir} already exists for idx: {merge_idx}"
                )
                if delete_workdir:
                    answer = "y"
                else:
                    answer = input(
                        f"Workdir {workdir} exists for idx: {merge_idx}. Delete it? (y/n)"
                    )
                if answer == "y":
                    os.system("chmod -R 777 " + str(WORKDIR_DIRECTORY / workdir))
                    shutil.rmtree(WORKDIR_DIRECTORY / workdir)
                else:
                    logger.info(
                        f"Workdir {WORKDIR_DIRECTORY/workdir} already exists. Skipping."
                    )
                    continue
            try:
                repo = Repository(
                    merge_idx=merge_idx,
                    repo_slug=repo_slug,
                    cache_directory=Path("no_cache/"),
                    workdir_id=str(workdir),
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
                timeout=TIMEOUT_MERGING,
                use_cache=False,
            )
            assert repo.local_repo_path.exists()

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
            if merge_result in (MERGE_STATE.Merge_failed, MERGE_STATE.Merge_success):
                # Run 'git diff --name-only --diff-filter=U' to get the files with conflicts
                process = subprocess.run(
                    ["git", "diff", "--name-only", "--diff-filter=U"],
                    cwd=repo.local_repo_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if len(process.stderr.decode("utf-8")) == 0:
                    conflict_files = process.stdout.decode("utf-8")
                    is_conflict = len(conflict_files) > 0
                    assert (
                        is_conflict == (merge_result == MERGE_STATE.Merge_failed)
                    ), f"merge_replay: tool{merge_tool} merge_result {merge_result} does not match conflict_files {conflict_files} at path {repo.local_repo_path}"

            result_df.loc[
                merge_tool.name,
                ["merge result", "merge log path", "repo path", "merge fingerprint"],
            ] = [
                merge_result.name,
                log_path,
                repo.local_repo_path,
                merge_fingerprint,
            ]
            assert repo.local_repo_path.exists()

            if (
                merge_result
                not in (
                    MERGE_STATE.Git_checkout_failed,
                    TEST_STATE.Git_checkout_failed,
                )
                and (
                    merge_data[f"{merge_tool.name}_merge_fingerprint"]
                    != merge_fingerprint
                    and not dont_check_fingerprints
                )
                and (merge_tool != MERGE_TOOL.spork)
                and (merge_tool != MERGE_TOOL.intellimerge)
                and (
                    merge_tool != MERGE_TOOL.gitmerge_resolve
                    or merge_result != MERGE_STATE.Merge_failed
                )
            ):
                assert repo.local_repo_path.exists()
                if create_artifacts:
                    store_artifacts(result_df)
                if delete_workdir:
                    delete_workdirs(result_df)
                print("=====================================\n")
                with open(log_path, "r", encoding="utf-8") as f:
                    print(f.read())
                print("=====================================\n")
                raise Exception(
                    f"fingerprints differ: after merge of {workdir} with {merge_tool}, found"
                    + f" {merge_fingerprint} but expected "
                    + f"{merge_data[f'{merge_tool.name}_merge_fingerprint']} at log path {log_path}"
                    + f" and repo path {repo.local_repo_path}",
                    merge_result,
                    f"idx {merge_idx}",
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
        if delete_workdir:
            del repo
    return result_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--merges_csv",
        help="CSV file with merges that have been tested",
        type=str,
        default="results/combined/result.csv",
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
    parser.add_argument(
        "-delete_workdir",
        help="Delete the workdir after replaying the merge",
        action="store_true",
    )
    parser.add_argument(
        "-dont_check_fingerprints",
        help="Don't check the fingerprint of a merge",
        action="store_true",
    )
    parser.add_argument(
        "-skip_build",
        help="Don't build the merge tool",
        action="store_false",
    )
    parser.add_argument(
        "-create_artifacts",
        help="Create artifacts",
        action="store_true",
    )
    parser.add_argument(
        "--testing",
        help="Run the script to only check for reproducibility",
        action="store_true",
    )
    args = parser.parse_args()

    logger.info(f"Replaying merge with index {args.idx}")
    if args.delete_workdir:
        logger.info("Deleting workdir after replaying the merge")
    if args.dont_check_fingerprints:
        logger.info("Not checking the fingerprint of a merge")
    if args.test:
        logger.info("Testing the replay of a merge")
    if args.create_artifacts:
        logger.info("Creating artifacts after replaying the merges")
    if not args.skip_build:
        logger.info("Building merge tool")
    if args.testing:
        logger.info("Checking for reproducibility")

    os.environ["PATH"] += os.pathsep + os.path.join(
        os.getcwd(), "src/scripts/merge_tools/merging/src/main/sh/"
    )
    os.environ["PATH"] += os.pathsep + os.path.join(
        os.getcwd(), "src/scripts/merge_tools"
    )
    os.environ["GIT_CONFIG_GLOBAL"] = os.getcwd() + "/.gitconfig"
    os.system("git submodule update --init")
    logger.info("finished git submodule update --init")
    if not args.skip_build:
        os.system("cd src/scripts/merge_tools/merging && ./gradlew -q shadowJar")

    df = pd.read_csv(args.merges_csv, index_col="idx")

    repo_slug = df.loc[args.idx, "repository"]
    merge_data = df.loc[args.idx]
    results_df = merge_replay(
        args.idx,
        str(repo_slug),
        merge_data,
        args.test,
        args.delete_workdir,
        args.create_artifacts,
        args.dont_check_fingerprints,
        args.testing,
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
