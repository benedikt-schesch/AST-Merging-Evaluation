#!/usr/bin/env python3

# usage: python3 repo_checker.py --repos_path <path_to_repo>
#                                         --output_path <output_path>
#
# This script takes a csv of repos and verifies that the top of main passes tests

import pandas as pd
from git import Repo
import subprocess
import shutil
import os
import multiprocessing
import git
import argparse
from tqdm import tqdm
import platform

CACHE = "cache/repos_result/"
WORKDIR = ".workdir/"
TIMEOUT_MERGE = 10 * 60

def get_repo(repo_name):
    repo_dir = "repos/" + repo_name
    if not os.path.isdir(repo_dir):
        git_url = "https://github.com/" + repo_name + ".git"
        repo = git.Repo.clone_from(git_url, repo_dir)
    else:
        repo = git.Git(repo_dir)
    try:
        repo.remote.fetch()
    except Exception:
        pass
    try:
        repo.remote().fetch()
    except Exception:
        pass
    return repo


def test_repo(repo_dir_copy, timeout):
    "Returns the return code of trying 3 times to run tester.sh on the given working copy."
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
            stderr=subprocess.DEVNULL
        ).returncode
        if rc == 0: # Success
            return 0
        if rc == 124:
            # Timeout
            return 124
    return 1


def check_repo(arg):
    idx, row = arg
    repo_name = row["repository"]
    print(repo_name,": Started")

    repo_dir = "repos/" + repo_name
    target_file = CACHE + repo_name.replace("/", "_") + ".csv"

    if os.path.isfile(target_file):
        df = pd.read_csv(target_file)
        print(repo_name,": Done, result is cached")
        return df.iloc[0]["test"]

    df = pd.DataFrame({"test": [1]})
    df.to_csv(target_file)
    pid = str(multiprocessing.current_process().pid)
    repo_dir_copy = WORKDIR + pid
    try:
        print(repo_name,": Cloning repo")
        repo = get_repo(repo_name)
        print(repo_name,": Finished cloning")
        shutil.copytree(repo_dir, repo_dir_copy)

        rc = test_repo(repo_dir_copy, TIMEOUT_MERGE)
        print("repo_name=" + repo_name + ", rc=" + rc)
        df = pd.DataFrame({"test": [rc]})
        df.to_csv(target_file)
    except Exception:
        pass
    shutil.rmtree(repo_dir_copy)
    print(repo_name,": Done")
    return df.iloc[0]["test"]


if __name__ == "__main__":
    print("repo_checker: Start")
    if not os.path.exists("cache"):
        os.mkdir("cache")
    if not os.path.exists(CACHE):
        os.mkdir(CACHE)

    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_path", type=str)
    parser.add_argument("--output_path", type=str)
    args = parser.parse_args()
    df = pd.read_csv(args.repos_path)

    print("repo_checker: Started Testing")
    pool = multiprocessing.Pool(processes=int(os.cpu_count()*0.75))
    r = list(tqdm(pool.imap(check_repo, df.iterrows()), total=len(df)))
    pool.close()
    print("repo_checker: Finished Testing")

    print("repo_checker: Building Output")
    out = []
    for idx, row in tqdm(df.iterrows()):
        repo_name = row["repository"]
        repo = check_repo((idx, row))
        if repo == 0:
            out.append(row)
    print("repo_checker: Finished Building Output")
    out = pd.DataFrame(out)
    out.to_csv(args.output_path)
    print("repo_checker: Done")
