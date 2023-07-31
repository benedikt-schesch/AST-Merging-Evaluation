""" Merges the cache files from two different caches.
Usage:
    python cache_merger.py --zip_cache <zip_cache> --target_cache <target_cache>

    zip_cache: path to the cache folder containing the zipped merge results
    target_cache: path to the cache folder containing the merge results

The script will unzip the zipped merge results and merge them with the
merge results in the target cache folder.
"""

import os
import argparse
import tarfile
import shutil
from pathlib import Path
from typing import Tuple
from merge_tester import MERGE_STATE
from tqdm import tqdm
from validate_repos import read_cache, write_cache, TEST_STATE

MERGE_ORDER = [
    MERGE_STATE.Tests_passed,
    MERGE_STATE.Tests_failed,
    MERGE_STATE.Tests_exception,
    MERGE_STATE.Tests_timedout,
    MERGE_STATE.Merge_failed,
    MERGE_STATE.Merge_exception,
    MERGE_STATE.Merge_timedout,
]

TEST_ORDER = [
    TEST_STATE.Tests_passed,
    TEST_STATE.Tests_failed,
    TEST_STATE.Tests_timedout,
    TEST_STATE.Failure_test_exception,
    TEST_STATE.Failure_repo_copy,
    TEST_STATE.Failure_git_checkout,
    TEST_STATE.Failure_git_clone,
    TEST_STATE.Not_tested,
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


def test_results_merger(
    test_state1: TEST_STATE,
    test_state2: TEST_STATE,
) -> TEST_STATE:
    """Merges the results of two caches."""
    for test_state in TEST_ORDER:
        if test_state2 == test_state:
            return test_state2
        if test_state1 == test_state:
            return test_state1
    raise Exception("Invalid Test State", test_state1, test_state2)


def merge_results_merger(
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


TMP_CACHE = ".old_cache"

if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--zip_cache", type=str, default="cache.tar")
    arg_parser.add_argument("--cache_path", type=str, default="cache/")
    args = arg_parser.parse_args()

    with tarfile.open(args.zip_cache, "r") as tar:
        tar.extractall(path=TMP_CACHE)

    # Test results merge status
    test_results_path = os.path.join(TMP_CACHE, "cache", "test_result")
    for file in tqdm(os.listdir(test_results_path)):
        if file.endswith(".txt") and not file.endswith("explanation.txt"):
            source_file = Path(os.path.join(test_results_path, file))
            target_file = Path(os.path.join(args.cache_path, "test_result", file))
            if not os.path.exists(target_file):
                print("Copying", source_file, "to", target_file)
                os.system(f"cp {source_file} {target_file}")
            else:
                test_state1, _ = read_cache(str(target_file).replace(".txt", ""))
                test_state2, _ = read_cache(str(source_file).replace(".txt", ""))
                test_state = test_results_merger(test_state1, test_state2)
                target_cache_file = str(target_file).replace(".txt", "")
                write_cache(test_state, "", target_cache_file)
                print("File already exists:", target_file)

    # Diffing merge test results
    merge_diff_results = os.path.join(TMP_CACHE, "cache", "merge_diff_results")
    for file in tqdm(os.listdir(merge_diff_results)):
        if file.endswith(".txt") and not file.endswith("explanation.txt"):
            source_file = Path(os.path.join(merge_diff_results, file))
            target_file = Path(
                os.path.join(args.cache_path, "merge_diff_results", file)
            )
            if not os.path.exists(target_file):
                print("Copying", source_file, "to", target_file)
                os.system(f"cp {source_file} {target_file}")

    # Merge test results
    merge_test_results_path = os.path.join(TMP_CACHE, "cache", "merge_test_results")
    for file in tqdm(os.listdir(merge_test_results_path)):
        if file.endswith(".txt") and not (
            file.endswith("explanation.txt")
        ):  # pylint: disable=C0325
            source_file = Path(os.path.join(merge_test_results_path, file))
            target_file = Path(
                os.path.join(args.cache_path, "merge_test_results", file)
            )
            if not os.path.exists(target_file):
                print("Copying", source_file, "to", target_file)
                os.system(f"cp {source_file} {target_file}")
            else:
                merge_state1, run_time1 = read_cache_merge_status(target_file)
                merge_state2, run_time2 = read_cache_merge_status(source_file)
                merge_state, run_time = merge_results_merger(
                    merge_state1, run_time1, merge_state2, run_time2
                )
                write_cache_merge_status(target_file, merge_state, run_time)
                print("File already exists:", target_file)

    shutil.rmtree(TMP_CACHE)
