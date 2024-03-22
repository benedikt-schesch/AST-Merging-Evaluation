"""Recreates merges on selection of algorithms with a selection of commits.
"""

import sys
import argparse
import os
from diff3_analysis import diff3_analysis


# Mixed conflict and pass examples from results_greatest_hits/result.csv
# Randomly chosen sample of mixed results from dataset
row_nums = [
    582,
    427,
    930,
    70,
    128,
    1444,
    1177,
    849,
    1425,
    1642,
    1897,
    862,
    943,
    1442,
    1120,
    111,
    693,
    535,
    354,
    530,
    845,
    654,
    921,
    464,
    1006,
    707,
    485,
    1928,
    809,
    1329,
    65,
    1890,
    100,
    247,
    2038,
    900,
]


# All merge tools
all_merge_tools = [
    "gitmerge_ort",
    "gitmerge_ort_adjacent",
    "gitmerge_ort_ignorespace",
    "gitmerge_ort_imports",
    "gitmerge_ort_imports_ignorespace",
    "gitmerge_resolve",
    "gitmerge_recursive_histogram",
    "gitmerge_recursive_ignorespace",
    "gitmerge_recursive_minimal",
    "gitmerge_recursive_myers",
    "gitmerge_recursive_patience",
    "git_hires_merge",
    "spork",
    "intellimerge",
]


# Default output directory for storing diff .txt files
base_output_dir = "./merge_conflict_analysis_diffs"


def run_analysis(
    rows=row_nums, merge_tools=all_merge_tools, output_dir=base_output_dir
):
    """
    Analyzes merge conflicts on a sample of repos with all merge algorithms.


    Returns:
        None
    """

    # Loop through each conflict, recreating merges to repo_output_dir
    for row_num in rows:
        for merge_tool in merge_tools:
            # Create a subdirectory for this specific results_index
            repo_output_dir = os.path.join(base_output_dir, str(row_num), merge_tool)
            os.makedirs(repo_output_dir, exist_ok=True)
            print(merge_tool)
            print(row_num)
            print(repo_output_dir)
            diff3_analysis(merge_tool, row_num, repo_output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run merge conflict analysis with optional parameters."
    )

    # Make arguments optional and provide default values
    parser.add_argument(
        "-m",
        "--merge_tool",
        type=str,
        nargs="*",
        choices=all_merge_tools,
        default=all_merge_tools,
        help="Comma-separated list of merge tools to be used. By default, all tools will be used.",
    )
    parser.add_argument(
        "-i",
        "--results_index",
        type=str,
        default=None,
        help="Comma-separated list of indices of repositories in results. Default: random list",
    )
    parser.add_argument(
        "-o",
        "--repo_output_dir",
        type=str,
        default=base_output_dir,
        help="Path to store results from analysis. Default: './merge_conflict_analysis_diffs'.",
    )

    args = parser.parse_args()

    # Parse the results_index to list of integers if provided
    rows_to_use = (
        [int(index) for index in args.results_index.split(",")]
        if args.results_index
        else row_nums
    )

    # Merge tools are directly accepted as a list due to nargs='*'
    tools_to_use = args.merge_tool

    os.makedirs(args.repo_output_dir, exist_ok=True)
    run_analysis(
        rows=rows_to_use, merge_tools=tools_to_use, output_dir=args.repo_output_dir
    )
