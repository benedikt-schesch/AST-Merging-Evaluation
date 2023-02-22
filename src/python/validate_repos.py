#!/usr/bin/env python3
"""Tests the HEAD of a repo and validates it if the test passes."""

# usage: python3 validate_repos.py --repos_path <repos.csv>
#                                         --output_path <valid_repos.csv>
#
# This script takes a csv of repos.
# It writes, to `valid_repos.csv`, those for which the head of main passes tests.
# The input file `repos.csv` must contain a header, one of whose columns is "repository".
# That column contains "ORGANIZATION/REPO" for a GitHub repository.

import subprocess
import shutil
import os
import multiprocessing
import argparse
import platform
from pathlib import Path

from tqdm import tqdm
from tqdm.contrib.concurrent import process_map
import pandas as pd
from git import Repo
import git

CACHE = "cache/repos_result/"
WORKDIR = ".workdir/"
TIMEOUT_MERGE = 30 * 60  # 30 minutes


def get_repo(repo_name):
    """Clones a repository
    Args:
        repo_name (str): The name of the repository to be cloned
    Returns:
        The repository
    """
    repo_dir = "repos/" + repo_name
    if not os.path.isdir(repo_dir):
        # @ in fron here to make sure that we are not prompted login details
        # for the repos that are now private
        git_url = "https://:@github.com/" + repo_name + ".git"
        repo = git.Repo.clone_from(git_url, repo_dir)
    else:
        repo = git.Repo(repo_dir)
    try:
        repo.remote().fetch()
    except Exception:
        pass
    return repo


def test_repo(repo_dir_copy, timeout):
    """Returns the return code of trying 3 times to run tester.sh on the given working copy.
    If one tests passes then the entire test is marked as passed.
    If one tests timeouts then the entire test is marked as timeout.
    Args:
        repo_dir_copy (str): The path of the repository.
        timeout (int): Test Timeout limit.
    Returns:
        int: The test value.
    """
    if platform.system() == "Linux":  # Linux
        command_timeout = "timeout"
    else:  # MacOS
        command_timeout = "gtimeout"
    for i in range(3):
        rc = subprocess.run(
            [
                command_timeout,
                str(timeout) + "s",
                "src/scripts/tester.sh",
                repo_dir_copy,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        if rc == 0:  # Success
            return 0
        if rc == 124:
            # Timeout
            return 124
    return 1


def check_repo(arg):
    """Checks if the head of main passes test.
    Args:
        arg (str): Information regarding that repo.
    Returns:
        int: 1 if the repo is valid (main head passes tests)
    """
    _, row = arg
    repo_name = row["repository"]
    print(repo_name, ": Started")
    result_interpretable = {0: "Valid", 1: "Not Valid", 124: "Not Valid Timeout"}

    repo_dir = "repos/" + repo_name
    target_file = CACHE + repo_name.replace("/", "_") + ".csv"

    df = pd.DataFrame({"test": [1]})
    pid = str(multiprocessing.current_process().pid)
    repo_dir_copy = WORKDIR + pid
    if os.path.isdir(repo_dir_copy):
        shutil.rmtree(repo_dir_copy)
    try:
        print(repo_name, ": Cloning repo")
        repo = get_repo(repo_name)
        print(repo_name, ": Finished cloning")

        # Check if result is cached
        if os.path.isfile(target_file):
            df = pd.read_csv(target_file)
            print(repo_name, ": ", result_interpretable[df.iloc[0]["test"]])
            print(repo_name, ": Done, result is cached")
            return df.iloc[0]["test"]

        print(repo_name, ": Testing")
        shutil.copytree(repo_dir, repo_dir_copy)
        rc = test_repo(repo_dir_copy, TIMEOUT_MERGE)
        df = pd.DataFrame({"test": [rc]})
        print(repo_name, ": Finished testing, result =", rc)
    except Exception:
        print(repo_name, ": Finished testing, result = exception")
        pass
    df.to_csv(target_file)
    if os.path.isdir(repo_dir_copy):
        shutil.rmtree(repo_dir_copy)
    print(repo_name, ": ", result_interpretable[df.iloc[0]["test"]])
    print(repo_name, ": Done")
    return df.iloc[0]["test"]


if __name__ == "__main__":
    Path("repos").mkdir(parents=True, exist_ok=True)
    Path(CACHE).mkdir(parents=True, exist_ok=True)
    Path(WORKDIR).mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_path", type=str)
    parser.add_argument("--output_path", type=str)
    args = parser.parse_args()
    df = pd.read_csv(args.repos_path)

    print("validate_repos: Started Testing")
    with multiprocessing.Pool(processes=int(os.cpu_count() * 0.75)) as pool:
        r = list(
            tqdm(
                pool.imap(check_repo, df.iterrows()),
                total=len(df),
            )
        )
    print("validate_repos: Finished Testing")

    print("validate_repos: Building Output")
    out = []
    for idx, row in tqdm(df.iterrows(), total=len(df)):
        repo_name = row["repository"]
        repo = check_repo((idx, row))
        if repo == 0:
            out.append(row)
    print("validate_repos: Finished Building Output")
    out = pd.DataFrame(out)
    out.to_csv(args.output_path)
    print("validate_repos: Number of valid repos:", len(out))
    print("validate_repos: Done")
