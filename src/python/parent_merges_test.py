#!/usr/bin/env python3
"""Tests the parents of a merge and subsamples merges from the merges with passing parents.

usage: python3 parent_merges_test.py --repos_csv <path_to_repos.csv>
                                     --merges_path <path_to_merges_directory>
                                     --output_dir <output_directory>
                                     --n_merges <max_number_of_merges>

This script takes a list of repositories and a path merges_path which contains a list of merges for 
each repository. The script verifies that the two parents of each merge has parents that pass tests.
It subsamples n_merges of merges that have passing parents for each repository.
The output is produced in <output_directory>.
"""

import shutil
import os
import itertools
import multiprocessing
from multiprocessing import Manager
import argparse
from pathlib import Path
import traceback

from validate_repos import repo_test, clone_repo, write_cache, read_cache, del_rw
from tqdm import tqdm
from functools import partialmethod
import pandas as pd
import git.repo

if os.getenv('TERM', 'dumb') == 'dumb':
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)


CACHE = "cache/commit_test_result/"
WORKDIR = ".workdir/"
TIMEOUT_TESTING = 30 * 60  # 30 minutes


def pass_test(repo_name, commit):
    """Checks if a certain commit in a repo passes tests.
    Uses a cache if it exists; otherwise creates the cache.
    Args:
        repo_name (str): Name of the repo to test.
        commit (str): Commit to test.
    Returns:
        str: Test result.
    """
    cache_file = os.path.join(CACHE, repo_name.split("/")[1] + "_" + commit + ".csv")

    if os.path.isfile(cache_file):
        status, _ = read_cache(cache_file)
        return status

    write_cache("Not tested", "Process started", cache_file)

    try:
        process = multiprocessing.current_process()
        pid = str(process.pid)

        repo_dir = os.path.join("repos/", repo_name)
        repo_dir_copy = os.path.join(WORKDIR, pid, "repo")

        repo = clone_repo(repo_name)

        if os.path.isdir(repo_dir_copy):
            shutil.rmtree(repo_dir_copy, onerror=del_rw)
        shutil.copytree(repo_dir, repo_dir_copy)
        repo = git.repo.Repo(repo_dir_copy)
        repo.remote().fetch()
        repo.submodule_update()

        result = "Success"
        explanation = ""

        try:
            repo.git.checkout(commit, force=True)
        except Exception as e:
            print(
                repo_name, commit, "Exception when checking out commit. Exception:\n", e
            )
            result = "Failure git checkout"
            explanation = "Unable to checkout " + commit + ": " + str(e)

        # Merges that are newer than that date should be ignored for reproducibility
        if result == "Success" and repo.commit().committed_date > 1677003361:
            result = "Failure commit date too new"
            explanation = "committed_date is too new: " + str(
                repo.commit().committed_date
            )

        if result == "Success":
            try:
                result, explanation = repo_test(repo_dir_copy, TIMEOUT_TESTING)
            except Exception as e:
                print(
                    repo_name,
                    commit,
                    "Exception when testing that commit. Exception:\n",
                    e,
                )
                result = "Failure exception during testing"
                explanation = str(e)

        write_cache(result, explanation, cache_file)
        if os.path.isdir(repo_dir_copy):
            shutil.rmtree(repo_dir_copy, onerror=del_rw)

        return result

    except Exception as e:
        print(
            repo_name,
            commit,
            "General exception when seting up testing. Exception:\n",
            e,
        )
        df = pd.DataFrame(
            {"Test result": "Failure general rxception", "Explanation": [str(e)]}
        )
        df.to_csv(cache_file)
        return "Failure General Exception"


def parent_pass_test(args):
    """Indicates whether the two parents of a merge pass tests. Only operates if no more than
        n_sampled other merges have passing parents.
    Args:
        repo_name (str): Name of the repo to test.
        left (str): Left parent hash of the merge.
        right (str): Right parent hash of the merge.
        merge (str): Hash of the merge.
        valid_merge_counter (str): Thread safe counter, counting number of valid merges.
        n_sampled (str): Number of sampled merges.
    Returns:
        str: Test result of left parent.
        str: Test result of right parent.
        str: Test result of the merge.
    """
    repo_name, left, right, merge, valid_merge_counter, n_sampled = args
    if valid_merge_counter[repo_name] > n_sampled:
        return "Enough tested merges", "Enough tested merges", "Enough tested merges"
    left_test = pass_test(repo_name, left)
    right_test = pass_test(repo_name, right)
    if left_test == "Success" and right_test == "Success":
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
    parser.add_argument("--repos_csv", type=str)
    parser.add_argument("--merges_path", type=str)
    parser.add_argument("--output_dir", type=str)
    parser.add_argument("--n_merges", type=int)
    args = parser.parse_args()
    df = pd.read_csv(args.repos_csv)
    if os.path.isdir(args.output_dir):
        shutil.rmtree(args.output_dir, onerror=del_rw)
    os.mkdir(args.output_dir)

    multiprocessing_manager = Manager()
    valid_merge_counter = multiprocessing_manager.dict()

    print("parent_merges_test: Constructing Inputs")
    tested_merges = []
    for _, repository_data in tqdm(df.iterrows(), total=len(df)):
        merges_repo = []
        repo_name = repository_data["repository"]
        valid_merge_counter[repo_name] = 0
        merge_list_file = os.path.join(
            args.merges_path, repo_name.split("/")[1] + ".csv"
        )
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(merge_list_file, names=["merge", "left", "right", "base"])
        merges = merges.sample(frac=1, random_state=42)

        for _, merge_data in merges.iterrows():
            merges_repo.append(
                (
                    repo_name,
                    merge_data["left"],
                    merge_data["right"],
                    merge_data["merge"],
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
    cpu_count = os.cpu_count() or 1
    processes_used = cpu_count - 2 if cpu_count > 3 else cpu_count
    with multiprocessing.Pool(processes=processes_used) as pool:
        r = list(tqdm(pool.imap(parent_pass_test, arguments), total=len(arguments)))
    print("parent_merges_test: Finished Testing")

    print("parent_merges_test: Constructing Output")
    for _, repository_data in tqdm(df.iterrows(), total=len(df)):
        repo_name = repository_data["repository"]
        merge_list_file = args.merges_path + repo_name.split("/")[1] + ".csv"

        if not os.path.isfile(merge_list_file):
            raise Exception(
                repo_name
                + " does not have a list of merge. Missing file: "
                + merge_list_file
            )

        merges = pd.read_csv(
            merge_list_file,
            names=["branch_name", "merge", "left", "right", "base"],
            header=0,
            index_col=False,
        )
        merges = merges.sample(frac=1, random_state=42)
        merges["parent test"] = ["Failure" for i in merges.iterrows()]
        merges["merge test"] = ["Failure" for i in merges.iterrows()]

        result = []
        counter = 0
        for merge_idx, merge_data in merges.iterrows():
            test_left, test_right, test_merge = parent_pass_test(
                (
                    repo_name,
                    merge_data["left"],
                    merge_data["right"],
                    merge_data["merge"],
                    {repo_name: 0},
                    0,
                )
            )
            merges.at[merge_idx, "merge test"] = test_merge
            if test_left == "Success" and test_right == "Success":
                merges.at[merge_idx, "parent test"] = "Success"
                counter += 1
                # Append the row to the result.
                result.append(merges.loc[merge_idx])  # type: ignore
            if counter >= args.n_merges:
                break
        result = pd.DataFrame(result)
        output_file = os.path.join(args.output_dir, repo_name.split("/")[1] + ".csv")
        result.to_csv(output_file)
    print("parent_merges_test: Finished Constructing Output")
    print("parent_merges_test: Done")
