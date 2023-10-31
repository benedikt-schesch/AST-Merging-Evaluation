#!/usr/bin/env python3
"""Write the hash of the HEAD of the default branch for each repository to its own file.
If the file already exists, do nothing.
After this is done, the resulting files are used indefinitely, for reproducible results.
The default branch is often named "main" or "master".

usage: python3 write_head_hashes.py --repos_csv <repos.csv>
                                    --output_path <repos_head_passes.csv>

Input: a csv of repos.
The input file `repos.csv` must contain a header, one of whose columns is "repository".
That column contains a slug ("ORGANIZATION/REPO") for a GitHub repository.
Output: Write one file per repository, with the hash of the HEAD of the default branch
as column "head hash".
"""

import os
import sys
import argparse
from pathlib import Path
import multiprocessing
from functools import partialmethod
from tqdm import tqdm
import pandas as pd
import git.repo
from variables import REPOS_PATH

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore


def clone_repo(repo_slug: str) -> git.repo.Repo:
    """Clones a repository, or runs `git fetch` if the repository is already cloned.
    Args:
        repo_slug (str): The slug of the repository, which is "owner/reponame".
    """
    repo_dir = REPOS_PATH / repo_slug.split("/")[1]
    if repo_dir.exists():
        repo = git.repo.Repo(repo_dir)
    else:
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        os.environ["GIT_TERMINAL_PROMPT"] = "0"
        print(repo_slug, " : Cloning repo")
        # ":@" in URL ensures that we are not prompted for login details
        # for the repos that are now private.
        github_url = "https://:@github.com/" + repo_slug + ".git"
        repo = git.repo.Repo.clone_from(github_url, repo_dir)
        print(repo_slug, " : Finished cloning")
        try:
            repo.remote().fetch()
            repo.submodule_update()
        except Exception as e:
            print(repo_slug, "Exception during cloning:\n", e)
            raise
    repo.remote().fetch("refs/pull/*/head:refs/remotes/origin/pull/*")
    return repo


def num_processes() -> int:
    """Compute the number of CPUs to be used
    Returns:
        int: the number of CPUs to be used.
    """
    cpu_count = os.cpu_count() or 1
    processes_used = int(0.7 * cpu_count) if cpu_count > 3 else cpu_count
    return processes_used


def get_latest_hash(args):
    """Collects the latest hash of the HEAD of the default branch for a repo.
    Args:
        Tuple[idx,row]: Information regarding that repo.
    Returns:
        pd.Series: repo information with the hash of the HEAD
    """
    _, row = args
    repo_slug = row["repository"]
    print("write_head_hashes:", repo_slug, ": Started get_latest_hash")

    try:
        print("write_head_hashes:", repo_slug, ": Cloning repo")
        repo = clone_repo(repo_slug)
        row["head hash"] = repo.head.commit.hexsha
    except Exception as e:
        print(
            "write_head_hashes:",
            repo_slug,
            ": Finished get_latest_hash, result = exception, cause:",
            e,
        )
        return None

    print("write_head_hashes:", repo_slug, ": Finished get_latest_hash")
    return row


if __name__ == "__main__":
    Path("repos").mkdir(parents=True, exist_ok=True)

    print("write_head_hashes: Started storing repo HEAD hashes")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_csv", type=Path)
    parser.add_argument("--output_path", type=Path)
    args = parser.parse_args()

    # If file exists ignore this step
    if os.path.isfile(args.output_path):
        print("write_head_hashes: Cached")
        sys.exit(0)

    df = pd.read_csv(args.repos_csv, index_col="idx")

    print("write_head_hashes: Started cloning repos and collecting head hashes")

    with multiprocessing.Pool(processes=num_processes()) as pool:
        get_latest_hash_result = list(
            tqdm(
                pool.imap(get_latest_hash, df.iterrows()),
                total=len(df),
            )
        )

    print("write_head_hashes: Finished cloning repos and collecting head hashes")

    result_df = pd.DataFrame([i for i in get_latest_hash_result if i is not None])
    result_df = result_df.reset_index(drop=True)
    print("write_head_hashes: Started storing repo HEAD hashes")
    result_df.to_csv(args.output_path, index_label="idx")
    print("write_head_hashes: Finished storing repo HEAD hashes")
