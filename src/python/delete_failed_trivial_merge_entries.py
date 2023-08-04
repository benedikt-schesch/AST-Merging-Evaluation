"""
This script deletes the entries in the cache that correspond to failed trivial merges.
Usage:
    python delete_trivial_merge_entries.py --results <results>
        results: path to the results csv file

The script will delete the entries in the cache that correspond to failed trivial merges.
"""
from argparse import ArgumentParser
import os
import sys
from tqdm import tqdm
from latex_output import (
    compute_incorrect_trivial_merges,
    MERGE_FAILURE_NAMES,
    MERGE_INCORRECT_NAMES,
)
from merge_tester import MERGE_TOOL, MERGE_STATE
import pandas as pd

if __name__ == "__main__":
    arg_parser = ArgumentParser()
    arg_parser.add_argument("--results", type=str, default="results/result.csv")
    arg_parser.add_argument(
        "--cache_path", type=str, default="cache/merge_test_results"
    )
    arg_parser.add_argument("-y", action="store_true", help="Skip confirmation prompt")
    args = arg_parser.parse_args()

    df = pd.read_csv(args.results)

    failed_trivial_merged = compute_incorrect_trivial_merges(df)
    print("Number of failed trivial merges:", len(failed_trivial_merged))

    to_delete = []
    for row in failed_trivial_merged:
        for merge_tool in MERGE_TOOL:
            if row[merge_tool] != MERGE_STATE.Tests_passed.name:
                cache_merge_status_prefix = os.path.join(
                    "cache",
                    "merge_test_results",
                    "_".join(
                        [
                            row["repo_name"].split("/")[1],
                            row["left"],
                            row["right"],
                            row["base"],
                            row["merge"],
                            "",
                        ]
                    ),
                )
                cache_merges_status = cache_merge_status_prefix + merge_tool + ".txt"
                to_delete.append(cache_merges_status)

    print("Number of failed entries to delete:", len(to_delete))
    if not args.y:
        print("Are you sure you want to proceed? (y/n)")
        if input() != "y":
            sys.exit(0)
    count = 0
    for file in tqdm(to_delete):
        if os.path.exists(file):
            os.remove(file)
            count += 1
            print("Deleted:", file)
    print("Deleted", count, "files")
    print("Done")
