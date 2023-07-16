"""
Delete entries in cache folder that lead to inconsistent merge results.
A merge result is considered inconsistent if it fails/pass for some merge tool
but for some other tool it timeouts or there is an exception during testing.
Usage:
    python delete_inconsistent_merge_results.py --results <results_path> --cache_path <cache_path>
        results_path: path to the csv file containing the merge results
        cache_path: path to the cache folder containing the merge results
"""
from argparse import ArgumentParser
import os
import sys
import glob
from tqdm import tqdm
from latex_output import MERGE_FAILURE_NAMES
from merge_tester import read_cache, MERGE_TOOLS
import pandas as pd

if __name__ == "__main__":
    arg_parser = ArgumentParser()
    arg_parser.add_argument("--results", type=str, default="results/result.csv")
    arg_parser.add_argument(
        "--cache_path", type=str, default="cache/merge_test_results"
    )
    args = arg_parser.parse_args()

    files_to_delete = []
    df = pd.read_csv(args.results)
    for _, row in tqdm(df.iterrows(), total=len(df)):
        n_failures = 0
        for i in MERGE_TOOLS:
            if row[f"{i}"] in MERGE_FAILURE_NAMES:
                n_failures += 1
        if 0 < n_failures < len(MERGE_TOOLS):
            files_to_delete.append(row)

    print("Number of inconsistent entries to delete:", len(files_to_delete))
    print("Are you sure you want to proceed? (y/n)")
    if input() != "y":
        sys.exit(0)
    for row in tqdm(files_to_delete):
        for i in MERGE_TOOLS:
            if row[f"{i}"] in MERGE_FAILURE_NAMES:
                cache_file = os.path.join(
                    args.cache_path,
                    row["repo_name"].split("/")[1]
                    + "_"
                    + row["left"]
                    + "_"
                    + row["right"]
                    + "_"
                    + row["base"]
                    + "_"
                    + row["merge"]
                    + "_"
                    + i,
                )
                if os.path.exists(cache_file + ".txt"):
                    os.remove(cache_file + ".txt")
                    if os.path.exists(cache_file + "_explanation.txt"):
                        os.remove(cache_file + "_explanation.txt")
                    print("Deleted:", cache_file + ".txt")
                else:
                    print("File not found:", cache_file)
    print("Done")
