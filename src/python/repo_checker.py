#!/usr/bin/env python3

# usage: python3 repo_checker.py --repos_path <path_to_repo>
#                                         --output_path <output_path>
#                                         --num_cpu <num_cpu_used>
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
        ).returncode
        if rc == 0:
            return 0
        if rc == 124:
            # Timeout
            return 124
    return 1


def check_repo(arg):
    print("called check_repo")

    idx, row = arg
    repo_name = row["repository"]

    print("repo_checker: check_repo("+str(idx)+", "+str(row)+"); repo_name="+str(repo_name))

    repo_dir = "repos/" + repo_name
    target_file = CACHE + repo_name.replace("/", "_") + ".csv"

    if os.path.isfile(target_file):
        df = pd.read_csv(target_file)
        return df.iloc[0]["test"]

    df = pd.DataFrame({"test": [1]})
    df.to_csv(target_file)
    pid = str(multiprocessing.current_process().pid)
    repo_dir_copy = WORKDIR + pid
    try:
        repo = get_repo(repo_name)
        shutil.copytree(repo_dir, repo_dir_copy)

        rc = test_repo(repo_dir_copy, TIMEOUT_MERGE)
        print("repo_name=" + repo_name + ", rc=" + rc))
        df = pd.DataFrame({"test": [rc]})
        df.to_csv(target_file)
    except Exception:
        pass
    shutil.rmtree(repo_dir_copy)
    return df.iloc[0]["test"]


if __name__ == "__main__":
    if not os.path.exists(CACHE):
        os.mkdir(CACHE)

    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_path", type=str)
    parser.add_argument("--output_path", type=str)
    parser.add_argument("--num_cpu", type=int)
    args = parser.parse_args()
    df = pd.read_csv(args.repos_path)
    print("len(df) " + str(len(df)))

    for idx, row in tqdm(df.iterrows(), total=len(df)):
        repo_name = row["repository"]
        repo = get_repo(repo_name)

    print("repo_checker: Start processing")
    pool = multiprocessing.Pool(processes=args.num_cpu)
    pool.map(check_repo, df.iterrows())
    pool.close()
    print("repo_checker: End processing")

    out = []
    for idx, row in df.iterrows():
        repo_name = row["repository"]
        repo = check_repo((idx, row))
        if repo == 0:
            out.append(row)
    out = pd.DataFrame(out)
    out.to_csv(args.output_path)
