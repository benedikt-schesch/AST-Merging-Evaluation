#!/usr/bin/env python3
"""Test the merges and check if the parents pass tests.
usage: python3 merge_tester.py --repos_head_passes_csv <path_to_repos_head_passes.csv>
                                --merges_path <path_to_merges>
                                --output_dir <output_dir>
                                --cache_dir <cache_dir>
This script checks if the parents pass tests and if so, it tests the merges with
each merge tool.
The output is written in output_dir and consists of the same merges as the input
but with the test results.
"""

import os
import multiprocessing
import argparse
import difflib
from pathlib import Path
from collections import defaultdict
from functools import partialmethod
from typing import Tuple, List, Dict
import random
import time
from xml.etree import ElementTree
import psutil
import pandas as pd
from cache_utils import lookup_in_cache, set_in_cache, slug_repo_name
from repo import Repository, MERGE_TOOL, TEST_STATE, MERGE_STATE
from write_head_hashes import num_processes
from tqdm import tqdm
from variables import (
    TIMEOUT_TESTING_MERGE,
    N_TESTS,
    TIMEOUT_MERGING,
)

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore


def parse_tested_lines(jacoco_xml: Path) -> Dict[str, List[int]]:
    """
    Parses the provided 'jacoco.xml' example and returns the files and lines that have been tested.
    """
    tested_lines = {}

    # Parse the XML string
    root = ElementTree.parse(jacoco_xml)

    # Iterate over source files
    for sourcefile in root.findall(".//sourcefile"):
        filename = sourcefile.get("name")
        file_lines = []

        # Iterate over lines in the source file
        for line in sourcefile.findall("line"):
            if (
                int(line.get("ci")) > 0  # type: ignore
            ):  # 'ci' attribute represents how many times the line was covered
                line_number = int(line.get("nr"))  # type: ignore
                file_lines.append(line_number)

        if file_lines:
            tested_lines[filename] = file_lines

    return tested_lines


def compare_files_with_reference(  # pylint: disable=too-many-locals
    path1: Path,
    path2: Path,
) -> Dict[str, List[int]]:
    """
    Compare files in two directories using path1 as the reference
    and return a list of files with their differing lines.
    This version uses the `difflib` library to find differences.
    """
    differences: Dict[str, List[int]] = defaultdict(list)

    # List all files in both directories
    files1 = {f for f in os.listdir(path1) if os.path.isfile(os.path.join(path1, f))}
    files2 = {f for f in os.listdir(path2) if os.path.isfile(os.path.join(path2, f))}

    # Find common files
    common_files = files1.intersection(files2)

    # Compare each file
    for file in common_files:
        file1 = os.path.join(path1, file)
        file2 = os.path.join(path2, file)

        with open(file1, "r") as f1, open(file2, "r") as f2:
            lines1 = f1.readlines()
            lines2 = f2.readlines()

        # Using difflib to find differences
        diff = difflib.unified_diff(
            lines1, lines2, fromfile=file1, tofile=file2, lineterm=""
        )
        curr_file = ""
        for line in diff:
            if line.startswith("---"):
                line = line.replace("---", "")
                curr_file = line.replace(f" {str(path1)}/", "")
            if line.startswith("@@"):
                # Extract line numbers part
                line_numbers = line.split(" ")[1]  # This gets the '-x,y' or '-x' part

                # Remove the leading '-' sign
                start_line = line_numbers.lstrip("-")

                # Check if there is a range indicated (x,y format)
                if "," in start_line:
                    start_line_number = int(
                        start_line.split(",")[0]
                    )  # Extract the starting line number
                    end_line_number = int(start_line.split(",")[1])
                else:
                    start_line_number = int(
                        start_line
                    )  # Convert the single number to an integer
                    end_line_number = start_line_number
                for i in range(start_line_number, end_line_number + 1):
                    differences[curr_file].append(i)
    # Add all lines that are only in path1
    for file in files1.difference(files2):
        file1 = os.path.join(path1, file)
        with open(file1, "r") as f1:
            lines1 = f1.readlines()
        for i in range(len(lines1)):
            differences[file].append(i)

    return differences


def check_if_lines_are_tested(
    differences: Dict[str, List[int]],
    tested_lines: Dict[str, List[int]],
) -> bool:
    """Checks if the lines in the differences are tested."""
    for file in differences.keys():
        tested_lines_in_file = tested_lines.get(file, [])
        for line in differences[file]:
            if line in tested_lines_in_file:
                return True
    return False


def merge_tester(  # pylint: disable=too-many-locals
    args: Tuple[str, pd.Series, Path]
) -> pd.Series:
    """Tests the parents of a merge and in case of success, it tests the merge.
    Args:
        args (Tuple[str,pd.Series,Path]): A tuple containing the repository slug,
                    the repository info, and the cache path.
    Returns:
        pd.Series: The result of the test.
    """
    repo_slug, merge_data, cache_directory = args
    while psutil.cpu_percent() > 90:
        print(
            "merge_tester: Waiting for CPU load to come down",
            repo_slug,
            merge_data["left"],
            merge_data["right"],
        )
        time.sleep(60)
    print("merge_tester: Started ", repo_slug, merge_data["left"], merge_data["right"])

    cache_key = merge_data["left"] + "_" + merge_data["right"]
    merge_cache_directory = cache_directory / "merge_tester"
    cache_data = lookup_in_cache(cache_key, repo_slug, merge_cache_directory, True)
    if cache_data is not None and isinstance(cache_data, dict):
        for key, value in cache_data.items():
            merge_data[key] = value
        return merge_data
    cache_data = {}

    repo_left = Repository(
        repo_slug,
        cache_directory=cache_directory,
        workdir_id=repo_slug + "/test-left-" + merge_data["left"],
    )
    repo_left.checkout(merge_data["left"])
    repo_right = Repository(
        repo_slug,
        cache_directory=cache_directory,
        workdir_id=repo_slug + "/test-right-" + merge_data["right"],
    )
    repo_right.checkout(merge_data["right"])

    for merge_tool in MERGE_TOOL:
        repo = Repository(
            repo_slug,
            cache_directory=cache_directory,
            workdir_id=repo_slug
            + f"/merge-tester-{merge_tool.name}-"
            + f'{merge_data["left"]}-{merge_data["right"]}',
        )
        (
            merge_result,
            merge_fingerprint,
            left_fingerprint,
            right_fingerprint,
            explanation,
            runtime,
        ) = repo.merge(
            merge_tool, merge_data["left"], merge_data["right"], timeout=TIMEOUT_MERGING
        )

        assert left_fingerprint == merge_data["left_tree_fingerprint"]
        assert right_fingerprint == merge_data["right_tree_fingerprint"]

        if merge_result == MERGE_STATE.Merge_success:
            diff_list = compare_files_with_reference(
                repo_left.repo_path, repo.repo_path
            )
            result, coverage = repo.test(
                TIMEOUT_TESTING_MERGE,
                N_TESTS,
            )
            if result in (TEST_STATE.Tests_passed, TEST_STATE.Tests_failed):
                test_xml_path = repo.repo_path / Path("target/site/jacoco/jacoco.xml")
                if test_xml_path.exists():
                    tested_lines = parse_tested_lines(test_xml_path)

                    cache_data[
                        f"{merge_tool.name} merge_lines_are_tested"
                    ] = check_if_lines_are_tested(diff_list, tested_lines)
                else:
                    cache_data[
                        f"{merge_tool.name} merge_lines_are_tested"
                    ] = "No test coverage data available"
        else:
            result = merge_result

        cache_data[merge_tool.name] = result.name
        cache_data[f"{merge_tool.name}_merge_fingerprint"] = merge_fingerprint

    set_in_cache(cache_key, cache_data, repo_slug, merge_cache_directory)
    for key, value in cache_data.items():
        merge_data[key] = value
    print("merge_tester: Finished", repo_slug, merge_data["left"], merge_data["right"])
    return merge_data


def build_arguments(
    args: argparse.Namespace,
    repo_slug: str,
) -> list:
    """Builds the arguments for the merge_tester function.
    Args:
        args (argparse.Namespace): The arguments of the script.
        repo_slug (str): The slug of the repository.
    Returns:
        list: The arguments for the merge_tester function.
    """
    merge_list_file = Path(
        os.path.join(args.merges_path, slug_repo_name(repo_slug) + ".csv")
    )
    output_file = Path(
        os.path.join(args.output_dir, slug_repo_name(repo_slug) + ".csv")
    )
    if not merge_list_file.exists():
        print(
            "merge_tester:",
            repo_slug,
            "does not have a list of merges. Missing file: ",
            merge_list_file,
        )
        return []

    if output_file.exists():
        print(
            "merge_tester: Skipping",
            repo_slug,
            "because it is already computed.",
        )
        return []
    try:
        merges = pd.read_csv(merge_list_file, header=0, index_col="idx")
    except pd.errors.EmptyDataError:
        print(
            "merge_tester: Skipping",
            repo_slug,
            "because it does not contain any merges.",
        )
        return []
    merges = merges[merges["sampled for testing"]]
    return [
        (repo_slug, merge_data, Path(args.cache_dir))
        for _, merge_data in merges.iterrows()
    ]


def main():  # pylint: disable=too-many-locals,too-many-statements
    """Main function"""
    print("merge_tester: Start")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_head_passes_csv", type=Path)
    parser.add_argument("--merges_path", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--cache_dir", type=Path, default="cache/")
    args = parser.parse_args()
    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    repos = pd.read_csv(args.repos_head_passes_csv, index_col="idx")

    print("merge_tester: Started collecting merges to test")
    merge_tester_arguments = []
    for _, repository_data in tqdm(repos.iterrows(), total=len(repos)):
        repo_slug = repository_data["repository"]
        merge_tester_arguments += build_arguments(args, repo_slug)

    # Shuffle input to reduce cache contention
    random.seed(42)
    random.shuffle(merge_tester_arguments)

    print("merge_tester: Finished collecting merges to test")
    print("merge_tester: Number of merges to test:", len(merge_tester_arguments))

    print("merge_tester: Started Testing")
    with multiprocessing.Pool(processes=num_processes()) as pool:
        merge_tester_results = list(
            tqdm(
                pool.imap(merge_tester, merge_tester_arguments),
                total=len(merge_tester_arguments),
            )
        )
    print("merge_tester: Finished Testing")

    repo_result = {repo_slug: [] for repo_slug in repos["repository"]}
    print("merge_tester: Started Writing Output")

    n_merges_parents_pass = 0
    for i in tqdm(range(len(merge_tester_arguments))):
        repo_slug = merge_tester_arguments[i][0]
        merge_results = merge_tester_results[i]
        if len(merge_results) > 0 and merge_results["parents pass"]:
            n_merges_parents_pass += 1
        repo_result[repo_slug].append(merge_results)

    n_total_merges = 0
    n_total_merges_parents_pass = 0
    for repo_slug in repo_result:
        output_file = Path(
            os.path.join(args.output_dir, slug_repo_name(repo_slug) + ".csv")
        )
        if output_file.exists():
            try:
                df = pd.read_csv(output_file, header=0)
            except pd.errors.EmptyDataError:
                print(
                    "merge_tester: Skipping",
                    repo_slug,
                    "because it does not contain any merges.",
                )
                continue
        else:
            df = pd.DataFrame(repo_result[repo_slug])
            df.sort_index(inplace=True)
            df.to_csv(output_file, index_label="idx")
        n_total_merges += len(df)
        n_total_merges_parents_pass += len(df[df["parents pass"]]) if len(df) > 0 else 0

    print("merge_tester: Number of newly tested merges:", len(merge_tester_arguments))
    print(
        'merge_tester: Number of newly tested merges with "parents pass":',
        n_merges_parents_pass,
    )
    print("merge_tester: Total number of tested merges:", n_total_merges)
    print(
        'merge_tester: Total number of merges with "parents pass":',
        n_total_merges_parents_pass,
    )
    print("merge_tester: Finished Writing Output")
    print("merge_tester: Done")


if __name__ == "__main__":
    main()
