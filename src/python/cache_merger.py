""" Merges the cache files from two different caches.
"""

import os
import argparse
from pathlib import Path
from typing import Tuple
from merge_tester import MERGE_STATE
from tqdm import tqdm

MERGE_ORDER = [
    MERGE_STATE.Tests_passed,
    MERGE_STATE.Tests_failed,
    MERGE_STATE.Tests_exception,
    MERGE_STATE.Tests_timedout,
    MERGE_STATE.Merge_failed,
    MERGE_STATE.Merge_exception,
    MERGE_STATE.Merge_timedout,
]


def write_cache_merge_status(path: Path, status: MERGE_STATE, run_time: float):
    """Writes the merge status to a cache file."""
    with open(path, "w") as f:
        f.write(status.name + "\n" + str(run_time))


def read_cache_merge_status(path: Path) -> Tuple[MERGE_STATE, float]:
    """Reads the merge status from a cache file."""
    with open(path, "r") as f:
        status_name = f.readline().strip()
        merge_state = MERGE_STATE[status_name]
        run_time = float(f.readline().strip())
    return merge_state, run_time


def merge_results(
    merge_state1: MERGE_STATE,
    run_time1: float,
    merge_state2: MERGE_STATE,
    run_time2: float,
):
    """Merges the results of two caches."""
    for merge_state in MERGE_ORDER:
        if merge_state2 == merge_state:
            return merge_state2, run_time2
        if merge_state1 == merge_state:
            return merge_state1, run_time1
    raise Exception("Invalid Merge State", merge_state1, merge_state2)


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        "--source_cache", type=str, default="cache2/cache/merge_test_results/"
    )
    arg_parser.add_argument(
        "--target_cache", type=str, default="cache/merge_test_results/"
    )
    args = arg_parser.parse_args()

    for file in tqdm(os.listdir(args.source_cache)):
        if file.endswith(".txt") and not (
            file.endswith("explanation.txt")
        ):  # pylint: disable=C0325
            source_file = os.path.join(args.source_cache, file)
            target_file = os.path.join(args.target_cache, file)
            if not os.path.exists(target_file):
                print("Copying", source_file, "to", target_file)
                os.system(f"cp {source_file} {target_file}")
                merge_state, run_time = read_cache_merge_status(source_file)
            else:
                merge_state1, run_time1 = read_cache_merge_status(target_file)
                merge_state2, run_time2 = read_cache_merge_status(source_file)
                merge_state, run_time = merge_results(
                    merge_state1, run_time1, merge_state2, run_time2
                )
                write_cache_merge_status(target_file, merge_state, run_time)
                print("File already exists:", target_file)
