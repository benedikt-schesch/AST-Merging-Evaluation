#!/usr/bin/env python3
""" Compare the results of two merge tools on the same merge.
usage: python3 merge_differ.py --repos_head_passes_csv <repos_head_passes_csv> 
                                --merges_path <merges_path>
                                --cache_dir <cache_dir>
This script compares the results of two merge tools on the same merge.
# TODO: Where is the output?  Standard out?
It outputs the diff of the two merge results if their results differ.
# TODO: Does "ignores" mean there is no output, or is it something deeper?
It ignores merges that have the same result or merges that are not successful.
"""

import os
import multiprocessing
import argparse
from pathlib import Path
from functools import partialmethod
from typing import Tuple, Union
import random
import subprocess
import pandas as pd
from repo import Repository, MERGE_TOOL, TEST_STATE, MERGE_STATE
from tqdm import tqdm
from write_head_hashes import num_processes
from cache_utils import slug_repo_name

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore

TIMEOUT_TESTING_PARENT = 60 * 30  # 30 minutes, in seconds
TIMEOUT_TESTING_MERGE = 60 * 45  # 45 minutes, in seconds


def get_merge_fingerprint(
    merge_data: pd.Series, merge_tool: MERGE_TOOL, cache_prefix: Path
) -> Union[Tuple[None, None], Tuple[Repository, str]]:
    """Returns the repo and the fingerprint of a merge,
    or (None, None) if the merge is not successful.
    Does some sanity-checking too.
    Args:
        merge_data: The merge data.
        merge_tool (str): The merge tool name.
    Returns:
        repo: the repo. None if the merge is not successful.
        str: the fingerprint of the merge. None if the merge is not successful.
    """
    if merge_data[merge_tool.name] not in (
        TEST_STATE.Tests_passed.name,
        TEST_STATE.Tests_failed.name,
    ):
        return None, None
    left = merge_data["left"]
    right = merge_data["right"]
    repo = Repository(repo_slug, cache_prefix=cache_prefix)
    (
        merge_status,
        merge_fingerprint,
        left_fingerprint,
        right_fingerprint,
        _,
        _,
    ) = repo.merge(
        tool=merge_tool,
        left_commit=left,
        right_commit=right,
        timeout=-1,
    )
    if merge_fingerprint is None:
        raise Exception(
            "merge_differ: Checkout failure",
            repo_slug,
            left,
            right,
            merge_tool.name,
        )
    assert merge_status == MERGE_STATE.Merge_success
    assert left_fingerprint == merge_data["left_tree_fingerprint"]
    assert right_fingerprint == merge_data["right_tree_fingerprint"]
    assert merge_fingerprint == merge_data[merge_tool.name + "_merge_fingerprint"]
    return (repo, merge_fingerprint)


def merge_differ(args: Tuple[pd.Series, Path]) -> None:
    # TODO: What does this funtion do with the diff?  I think it writes to a file?  Or does it populate a cache too?
    """Diffs the results of every two merge tools on the same merge.
    Does not diff merges that have the same result or merges that are not successful.
    Args:
        args (Tuple[pd.Series,Path]): A tuple containing the merge data and the cache prefix.
    Returns:
        TODO: How is "The result of the test." related to the diff of two merge tools?  I don't see this function returning anything.
        dict: The result of the test.
    """
    merge_data, cache_prefix = args

    if not merge_data["parents pass"]:
        return

    # TODO: See other comment about "_prefix" in variable names; change throughout.
    diff_file_prefix = cache_prefix / "merge_diffs"
    diff_file_prefix.mkdir(parents=True, exist_ok=True)

    for merge_tool1 in MERGE_TOOL:
        repo1, merge_fingerprint1 = get_merge_fingerprint(
            merge_data, merge_tool1, cache_prefix
        )
        if repo1 is None or merge_fingerprint1 is None:
            continue

        for merge_tool2 in MERGE_TOOL:
            repo2, merge_fingerprint2 = get_merge_fingerprint(
                merge_data, merge_tool2, cache_prefix
            )
            if repo2 is None or merge_fingerprint2 is None:
                continue

            diff_file = diff_file_prefix / diff_file_name(
                merge_fingerprint1, merge_fingerprint2
            )
            if diff_file.exists():
                continue
            command = ["diff", "-u", "-r", "-x", "*/\\.git*"]
            command.append(str(repo1.repo_path))
            command.append(str(repo2.repo_path))
            with open(diff_file, "w") as f:
                subprocess.run(command, stdout=f, stderr=f)
            del repo2
        del repo1


def diff_file_name(sha1: str, sha2: str) -> Path:
    """Returns the name of the diff file.
    Args:
        sha1 (str): The first sha.
        sha2 (str): The second sha.
    Returns:
        Path: The name of the diff file.
    """
    # Use lexicographic order to prevent duplicates
    if sha1 < sha2:
        # TODO: Why does this use ".txt" rather than ".diff" as the file extension?
        return Path(sha1 + "_" + sha2 + ".txt")
    return Path(sha2 + "_" + sha1 + ".txt")


if __name__ == "__main__":
    print("merge_differ: Start")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_head_passes_csv", type=Path)
    parser.add_argument("--merges_path", type=Path)
    parser.add_argument("--cache_dir", type=Path, default="cache/")
    args = parser.parse_args()
    cache_dir = Path(args.cache_dir)
    # TODO: See comment elsewhere about "_path" in variable names.
    cache_diffs_path = cache_dir / "merge_diffs"
    cache_diffs_path.mkdir(parents=True, exist_ok=True)

    repos = pd.read_csv(args.repos_head_passes_csv, index_col="idx")

    print("merge_differ: Started collecting diffs to compute")
    merge_differ_arguments = []
    for _, repository_data in tqdm(repos.iterrows(), total=len(repos)):
        merges_repo = []
        repo_slug = repository_data["repository"]
        merge_list_file = Path(
            os.path.join(args.merges_path, slug_repo_name(repo_slug) + ".csv")
        )
        if not merge_list_file.exists():
            print(
                "merge_differ.py:",
                repo_slug,
                "does not have a list of merges. Missing file: ",
                merge_list_file,
            )
            continue

        try:
            merges = pd.read_csv(merge_list_file, header=0, index_col="idx")
        except pd.errors.EmptyDataError:
            print(
                "merge_differ.py: Skipping",
                repo_slug,
                "because it does not contain any merges.",
            )
            continue
        for _, merge_data in merges.iterrows():
            need_to_diff = False
            for merge_tool1 in MERGE_TOOL:
                if merge_data[merge_tool1.name] not in (
                    TEST_STATE.Tests_passed.name,
                    TEST_STATE.Tests_failed.name,
                ):
                    continue
                for merge_tool2 in MERGE_TOOL:
                    if merge_data[merge_tool2.name] not in (
                        TEST_STATE.Tests_passed.name,
                        TEST_STATE.Tests_failed.name,
                    ):
                        continue
                    if (
                        merge_data[merge_tool1.name + "_merge_fingerprint"]
                        == merge_data[merge_tool2.name + "_merge_fingerprint"]
                    ):
                        continue
                    file_name = cache_diffs_path / diff_file_name(
                        merge_data[merge_tool1.name + "_merge_fingerprint"],
                        merge_data[merge_tool2.name + "_merge_fingerprint"],
                    )
                    if not file_name.exists():
                        need_to_diff = True
            if need_to_diff:
                merge_differ_arguments.append((repo_slug, merge_data, cache_dir))

    # Shuffle input to reduce cache contention
    random.seed(42)
    random.shuffle(merge_differ_arguments)

    print("merge_differ: Finished collecting diffs to compute")
    print("merge_differ: Number of merges to test:", len(merge_differ_arguments))

    print("merge_differ: Started Diffing")
    with multiprocessing.Pool(processes=num_processes()) as pool:
        tqdm(
            pool.imap(merge_differ, merge_differ_arguments),
            total=len(merge_differ_arguments),
        )
    print("merge_differ: Finished Diffing")
