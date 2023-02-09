#!/usr/bin/env python3

# usage: python3 test_parent_merges.py --repos_path <path_to_repo>
#                                         --merges_path <path_to_merges>
#                                         --output_dir <output_directory>
#                                         --n_merges <max_number_of_merges>
#
# This script takes a list of merges and verifies that the two parents of each merge
# has parents that pass tests.
# It produces output into <output_directory>.

import shutil
import os
import itertools
import multiprocessing
from multiprocessing import Manager
import argparse
from pathlib import Path

from repo_checker import test_repo, get_repo
from tqdm import tqdm
import pandas as pd
import git

CACHE = "cache/commit_test_result/"
WORKDIR = ".workdir/"
TIMEOUT_SECONDS = 30 * 60  # 30 minutes


def pass_test(repo_name, commit):
    """Checks if a certain commit in a repo passes tests.
    Args:
        repo_name (str): Name of the repo to test.
        commit (str): Commit to test.
    Returns:
        int: Test result.
    """
    cache_file = CACHE + repo_name.split("/")[1] + "_" + commit

    if os.path.isfile(cache_file):
        try:
            with open(cache_file) as f:
                return int(next(f))
        except Exception:
            return 1

    try:
        process = multiprocessing.current_process()
        pid = str(process.pid)

        repo_dir = "repos/" + repo_name
        repo_dir_copy = WORKDIR + pid

        repo = get_repo(repo_name)

        if os.path.isdir(repo_dir_copy):
            shutil.rmtree(repo_dir_copy)
        shutil.copytree(repo_dir, repo_dir_copy)
        repo = git.Git(repo_dir_copy)
        repo.fetch()

        try:
            repo.checkout(commit)
            try:
                test = test_repo(repo_dir_copy, TIMEOUT_SECONDS)
            except Exception:
                test = 2
        except Exception:
            test = 3

        with open(cache_file, "w") as f:
            f.write(str(test))
        shutil.rmtree(repo_dir_copy)

        return test

    except Exception:
        with open(cache_file, "w") as f:
            f.write(str(-1))
        return -1


def valid_merge(args):
    """Verifies that the two parents of a merge pass tests. Only operates if no more than
        n_sampled other merges have passing parents.
    Args:
        repo_name (str): Name of the repo to test.
        left (str): Left parent hash of a merge.
        right (str): Right parent hash of a merge.
        merge (str): Hash of the merge.
        valid_merge_counter (str): Thread safe counter, counting number of valid merges.
        n_sampled (str): Number of sampled merges.
    Returns:
        int: Test result of left parent.
        int: Test result of right parent.
        int: Test result of the merge.
    """
    repo_name, left, right, merge, valid_merge_counter, n_sampled = args
    if valid_merge_counter[repo_name] > n_sampled + 10:
        return
    left_test = pass_test(repo_name, left)
    right_test = pass_test(repo_name, right)
    if left_test == 0 and right_test == 0:
        valid_merge_counter[repo_name] = valid_merge_counter[repo_name] + 1
    merge_test = pass_test(repo_name, merge)
    return left_test, right_test, merge_test


if __name__ == "__main__":
    print("test_parent_merges: Start")
    Path("repos").mkdir(parents=True, exist_ok=True)
    Path("cache").mkdir(parents=True, exist_ok=True)
    Path(CACHE).mkdir(parents=True, exist_ok=True)
    Path(WORKDIR).mkdir(parents=True, exist_ok=True)

    pwd = os.getcwd()
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_path", type=str)
    parser.add_argument("--merges_path", type=str)
    parser.add_argument("--output_dir", type=str)
    parser.add_argument("--n_merges", type=int)
    args = parser.parse_args()
    df = pd.read_csv(args.repos_path)
    if os.path.isdir(args.output_dir):
        shutil.rmtree(args.output_dir)
    os.mkdir(args.output_dir)

    manager = Manager()
    valid_merge_counter = manager.dict()

    print("test_parent_merges: Constructing Inputs")
    tested_merges = []
    for idx, row in tqdm(df.iterrows(), total=len(df)):
        merges_repo = []
        repo_name = row["repository"]
        valid_merge_counter[repo_name] = 0
        merge_list_file = args.merges_path + repo_name.split("/")[1] + ".csv"
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(merge_list_file, names=["merge", "left", "right", "base"])
        merges = merges.sample(frac=1, random_state=42)

        for idx2, row2 in merges.iterrows():
            if len(row2["left"]) == 40 and len(row2["right"]) == 40:
                merges_repo.append(
                    (
                        repo_name,
                        row2["left"],
                        row2["right"],
                        row2["merge"],
                        valid_merge_counter,
                        args.n_merges,
                    )
                )
        tested_merges.append(merges_repo)
    print("test_parent_merges: Finished Constructing Inputs")

    # Interleave testing to reduce probability that tests at the same hash happen in parallel
    arguments = [
        val
        for l in itertools.zip_longest(*tested_merges)
        for val in l
        if val is not None
    ]
    assert len(arguments) == sum(len(l) for l in tested_merges)

    print("test_parent_merges: Number of tested commits:", len(arguments))
    print("test_parent_merges: Started Testing")
    with multiprocessing.Pool(processes=int(os.cpu_count() * 0.75)) as pool:
        r = list(tqdm(pool.imap(valid_merge, arguments), total=len(arguments)))
    print("test_parent_merges: Finished Testing")

    print("test_parent_merges: Constructing Output")
    for idx, row in tqdm(df.iterrows(), total=len(df)):
        repo_name = row["repository"]
        merge_list_file = args.merges_path + repo_name.split("/")[1] + ".csv"
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(
            merge_list_file,
            names=["branch_name", "merge", "left", "right", "base"],
            header=0,
            index_col=False,
        )
        merges = merges.sample(frac=1, random_state=42)
        merges["parent test"] = [1 for i in merges.iterrows()]
        merges["merge test"] = [1 for i in merges.iterrows()]

        result = []
        counter = 0
        for idx2, row2 in merges.iterrows():
            if len(row2["left"]) == 40 and len(row2["right"]) == 40:
                test_left, test_right, test_merge = valid_merge(
                    (
                        repo_name,
                        row2["left"],
                        row2["right"],
                        row2["merge"],
                        {repo_name: 0},
                        0,
                    )
                )
                merges.loc[idx2, "merge test"] = test_merge
                if test_left == 0 and test_right == 0:
                    merges.loc[idx2, "parent test"] = 0
                    counter += 1
                    result.append(merges.loc[idx2])
                if counter >= args.n_merges:
                    break
        result = pd.DataFrame(result)
        outout_file = args.output_dir + repo_name.split("/")[1] + ".csv"
        result.to_csv(outout_file)
    print("test_parent_merges: Finished Constructing Output")
    print("test_parent_merges: Done")
