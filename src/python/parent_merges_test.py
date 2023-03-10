#!/usr/bin/env python3
"""Tests the parents of a merge and subsamples merges from the merges with passing parents."""

# usage: python3 parent_merges_test.py --repos_path <path_to_repo>
#                                         --merges_path <path_to_merges>
#                                         --output_dir <output_directory>
#                                         --n_merges <max_number_of_merges>
#
# This script takes a list of merges for each repository and verifies that the two parents
# of each merge has parents that pass tests. It subsamples n_merges of merges that have passing
# parents for each repository.
# It produces output in <output_directory>.

import shutil
import os
import itertools
import multiprocessing
from multiprocessing import Manager
import argparse
from pathlib import Path

from validate_repos import repo_test, get_repo
from tqdm import tqdm
import pandas as pd
import git

CACHE = "cache/commit_test_result/"
WORKDIR = ".workdir/"
TIMEOUT_SECONDS = 30 * 60  # 30 minutes


def pass_test(repo_name, commit):
    """Checks if a certain commit in a repo passes tests.
    Uses a cache if it exists; otherwise creates the cache.
    Args:
        repo_name (str): Name of the repo to test.
        commit (str): Commit to test.
    Returns:
        int: Test result.
    """
    cache_file = CACHE + repo_name.split("/")[1] + "_" + commit

    if os.path.isfile(cache_file):
        with open(cache_file) as f:
            return int(next(f).split(" ")[0])

    try:
        process = multiprocessing.current_process()
        pid = str(process.pid)

        repo_dir = "repos/" + repo_name
        repo_dir_copy = WORKDIR + pid + "/repo"

        repo = get_repo(repo_name)

        if os.path.isdir(repo_dir_copy):
            shutil.rmtree(repo_dir_copy)
        shutil.copytree(repo_dir, repo_dir_copy)
        repo = git.Repo(repo_dir_copy)
        repo.remote().fetch()

        result = 0
        explanation = ""

        try:
            repo.git.checkout(commit, force=True)
        except Exception as e:
            print(
                repo_name, commit, "Exception when checking out commit. Exception:\n", e
            )
            result = 3
            explanation = "Unable to checkout " + commit + ": " + str(e)

        # Merges that are newer than that date should be ignored for reproducibility
        if result == 0 and repo.commit().committed_date > 1677003361:
            result = 3
            explanation = "committed_date is too new: " + repo.commit().committed_date

        if result == 0:
            try:
                result, explanation = repo_test(repo_dir_copy, TIMEOUT_SECONDS)
            except Exception as e:
                print(
                    repo_name,
                    commit,
                    "Exception when testing that commit. Exception:\n",
                    e,
                )
                result = 2
                explanation = str(e)

        with open(cache_file, "w") as f:
            f.write(str(result) + " ")
            f.write(explanation)
        if os.path.isdir(repo_dir_copy):
            shutil.rmtree(repo_dir_copy)

        return result

    except Exception as e:
        print(
            repo_name,
            commit,
            "General exception when seting up testing. Exception:\n",
            e,
        )
        with open(cache_file, "w") as f:
            f.write(str(-1) + " ")
            f.write(" " + str(e))
            f.write(traceback.format_exc())
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
    if valid_merge_counter[repo_name] > n_sampled:
        return 3, 3, 3
    left_test = pass_test(repo_name, left)
    right_test = pass_test(repo_name, right)
    if left_test == 0 and right_test == 0:
        valid_merge_counter[repo_name] = valid_merge_counter[repo_name] + 1
    merge_test = pass_test(repo_name, merge)
    return left_test, right_test, merge_test


if __name__ == "__main__":
    print("parent_merges_test: Start")
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

    print("parent_merges_test: Constructing Inputs")
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
    print("parent_merges_test: Finished Constructing Inputs")

    # `zip_longest` interleaves testing to reduce probability that tests at the same hash happen in
    # parallel.
    arguments = [
        val
        for l in itertools.zip_longest(*tested_merges)
        for val in l
        if val is not None
    ]
    assert len(arguments) == sum(len(l) for l in tested_merges)

    print("parent_merges_test: Number of tested commits:", len(arguments))
    print("parent_merges_test: Started Testing")
    with multiprocessing.Pool(processes=int(os.cpu_count() * 0.75)) as pool:
        r = list(tqdm(pool.imap(valid_merge, arguments), total=len(arguments)))
    print("parent_merges_test: Finished Testing")

    print("parent_merges_test: Constructing Output")
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
    print("parent_merges_test: Finished Constructing Output")
    print("parent_merges_test: Done")
