#!/usr/bin/env python3

# usage: python3 test_parent_merges.py --repos_path <path_to_repo>
#                                         --merges_path <path_to_merges>
#                                         --output_dir <output_directory>
#                                         --n_merges <max_number_of_merges>
#
# This script takes a list of merges and verifies that the two parents of each merge
# has parents that pass tests.

import pandas as pd
import git
import shutil
import os
import multiprocessing
from multiprocessing import Manager
import argparse
from repo_checker import test_repo, get_repo

CACHE = "cache/commit_test_result/"
WORKDIR = ".workdir/"
TIMEOUT_SECONDS = 10 * 60


def pass_test(repo_name, commit):
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

    if not os.path.isdir(CACHE):
        os.mkdir(CACHE)

    manager = Manager()
    valid_merge_counter = manager.dict()

    tested_merges = []
    for idx, row in df.iterrows():
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

    # Interleave testing to reduce probability that tests at the same hash happen in parallel
    tested_merges = [val for l in zip(tested_merges) for val in l]

    print("Number of tested commits:", len(tested_merges))
    print("Started Testing")
    pool = multiprocessing.Pool(processes=int(os.cpu_count()*0.75))
    result = pool.map(valid_merge, tested_merges)
    pool.close()
    print("Finished Testing")

    for idx, row in df.iterrows():
        repo_name = row["repository"]
        merge_list_file = args.merges_path + repo_name.split("/")[1] + ".csv"
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(
            merge_list_file,
            names=["merge", "left", "right", "base"],
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
