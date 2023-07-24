"""
Delete entries in cache folder that match a certain state.
Usage:
    python delete_cache_entries.py --cache_path <cache_path>
        cache_path: path to the cache folder containing the merge results
"""
from argparse import ArgumentParser
import os
import sys
import glob
from tqdm import tqdm
from validate_repos import TEST_STATE, read_cache
from merge_tester import MERGE_TOOL


STATE_TO_DELETE = [
    TEST_STATE.Not_tested,
]

MERGE_TOOLS_DIFFS = ("gitmerge-ort", "gitmerge-ort-ignorespace")

if __name__ == "__main__":
    arg_parser = ArgumentParser()
    arg_parser.add_argument("--cache_path", type=str, default="cache")
    args = arg_parser.parse_args()

    files_to_delete = []
    diff_cache_path = os.path.join(args.cache_path, "merge_diff_results")
    for path in tqdm(glob.glob(f"{diff_cache_path}/*")):
        if os.path.isdir(path):
            continue
        if MERGE_TOOLS_DIFFS[0] not in path and MERGE_TOOLS_DIFFS[1] not in path:
            continue
        with open(path, "r") as f:
            lines = f.readlines()
        status = lines[0].strip() == "True"
        if status:
            continue
        files_to_delete.append(path)

    print("Number of files from diff cache to delete:", len(files_to_delete))
    print("Are you sure you want to proceed? (y/n)")
    if input() != "y":
        sys.exit(0)
    for path in files_to_delete:
        os.remove(path)
    print("Done")

    files_to_delete = []
    for path in tqdm(glob.glob(f"{args.cache_path}/*")):
        if os.path.isdir(path):
            continue
        if path.endswith("_explanation.txt"):
            continue
        path = path[:-4]
        status, explanation = read_cache(path)
        if status in STATE_TO_DELETE:
            files_to_delete.append(path)

    print("Number of files to delete:", len(files_to_delete))
    print("Are you sure you want to proceed? (y/n)")
    if input() != "y":
        sys.exit(0)
    for path in files_to_delete:
        os.remove(path + ".txt")
        if os.path.exists(path + "_explanation.txt"):
            os.remove(path + "_explanation.txt")
    print("Done")
