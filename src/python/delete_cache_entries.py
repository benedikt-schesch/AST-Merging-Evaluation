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


STATE_TO_DELETE = [
    TEST_STATE.Not_tested,
]

if __name__ == "__main__":
    arg_parser = ArgumentParser()
    arg_parser.add_argument("--cache_path", type=str, default="cache/test_result")
    args = arg_parser.parse_args()

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
