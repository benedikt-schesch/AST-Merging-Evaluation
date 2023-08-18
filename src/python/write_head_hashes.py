#!/usr/bin/env python3
"""Write the hash of the HEAD of the default branch for each repository to its own file.
If the file already exists, do nothing.
After this is done, the resulting files are used indefinitely, for reproducible results.
Note: the default branch is often named "main" or "master".

usage: python3 write_head_hashes.py --repos_csv <repos.csv>
                                    --output_path <valid_repos.csv>

Input: a csv of repos.
The input file `repos.csv` must contain a header, one of whose columns is "repository".
That column contains "ORGANIZATION/REPO" for a GitHub repository.
Output: Write one file per repository, with the hash of the HEAD of the default branch
as column "Validation hash".
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
import pandera as pa

# define input schema
schema = pa.DataFrameSchema({
    "repository": pa.Column(str),
    "language": pa.Column(str),
    "architecture": pa.Column(float),
    "continuous_integration": pa.Column(int),
    "documentation": pa.Column(float),
    "history":pa.Column(float),
    "issues":pa.Column(float),
    "license":pa.Column(int),
    "size":pa.Column(int),
    "unit_test":pa.Column(float),
    "stars":pa.Column(int),
    "scorebased_org":pa.Column(int),
    "randomforest_org":pa.Column(int),
    "scorebased_utl":pa.Column(int),
    "randomforest_utl":pa.Column(int)
})

def clone_repo(repo_slug: str) -> git.repo.Repo:
    """Clones a repository, or runs `git fetch` if it is already cloned.
    Args:
        repo_slug (str): The name of the repository to be cloned
    """
    repo_dir = REPOS_PATH / repo_slug
    if repo_dir.exists():
        repo = git.repo.Repo(repo_dir)
    else:
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        # ":@" in URL ensures that we are not prompted for login details
        # for the repos that are now private.
        os.environ["GIT_TERMINAL_PROMPT"] = "0"
        print(repo_slug, " : Cloning repo")
        git_url = "https://:@github.com/" + repo_slug + ".git"
        repo = git.repo.Repo.clone_from(git_url, repo_dir)
        print(repo_slug, " : Finished cloning")
        try:
            repo.remote().fetch()
            repo.submodule_update()
        except Exception as e:
            print(repo_slug, "Exception during cloning. Exception:\n", e)
            raise
    return repo


def compute_num_cpus_used(ratio: float = 0.7) -> int:
    """Comput the number of cpus to be used
    Args:
        ratio (float) = 0.7: Ratios of cpus to be used with respect
            to the total number of cpus.
    Returns:
        int: the number of cpus to be used.
    """
    cpu_count = os.cpu_count() or 1
    processes_used = int(ratio * cpu_count) if cpu_count > 3 else cpu_count
    return processes_used


if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore


def get_latest_hash(args):
    """Collects the latest hash of the HEAD of the default branch for a repo.
    Args:
        arg (idx,row): Information regarding that repo.
    Returns:
        pd.Series: repo information with the hash of the HEAD
    """
    _, row = args
    repo_slug = row["repository"]
    print(repo_slug, ": Started get_latest_hash")

    try:
        print(repo_slug, ": Cloning repo")
        repo = clone_repo(repo_slug)
        row["Validation hash"] = repo.head.commit.hexsha
    except Exception as e:
        print(repo_slug, ": Finished testing, result = exception, cause:", e)
        return None

    print(repo_slug, ": Finished get_latest_hash")
    return row


if __name__ == "__main__":
    Path("repos").mkdir(parents=True, exist_ok=True)

    print("Started storing repo HEAD hashes")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_csv", type=Path)
    parser.add_argument("--output_path", type=Path)
    args = parser.parse_args()

    # If file exists ignore this step
    if os.path.isfile(args.output_path):
        print("validate_repos: Cached")
        sys.exit(0)

    df = pd.read_csv(args.repos_csv,index_col="idx")
    df = schema(df)

    print("write_head_hashes: Started cloning repos and collecting head hashes")

    with multiprocessing.Pool(processes=compute_num_cpus_used()) as pool:
        get_latest_hash_result = list(
            tqdm(
                pool.imap(get_latest_hash, df.iterrows()),
                total=len(df),
            )
        )

    result_df = pd.DataFrame([i for i in get_latest_hash_result if i is not None])
    result_df = result_df.set_index(result_df.columns[0]).reset_index(drop=True)
    result_df.to_csv(args.output_path, index_label="idx")
    print("Finished Storing Repos Hashes")
