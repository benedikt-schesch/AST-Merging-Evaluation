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
Output: Write one file per repository, with the hash of the HEAD of the default branch.
"""

import os
import sys
import argparse
from pathlib import Path
import multiprocessing
from functools import partialmethod
from validate_repos import clone_repo
from tqdm import tqdm
import pandas as pd

if os.getenv("TERM", "dumb") == "dumb":
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore


def get_latest_hash(args):
    """Collects the latest hash of the HEAD of the default branch for a repo.
    Args:
        arg (idx,row): Information regarding that repo.
    Returns:
        pd.Series: repo infromation with the hash of the HEAD
    """
    _, row = args
    repo_name = row["repository"]
    print(repo_name, ": Started get_latest_hash")

    try:
        print(repo_name, ": Cloning repo")
        repo = clone_repo(repo_name)
        row["Validation hash"] = repo.head.commit.hexsha
    except Exception as e:
        print(repo_name, ": Finished testing, result = exception, cause:", e)
        return None

    print(repo_name, ": Finished get_latest_hash")
    return row


if __name__ == "__main__":
    Path("repos").mkdir(parents=True, exist_ok=True)

    print("Started Storing Repos Hashes")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_csv", type=Path)
    parser.add_argument("--output_path", type=Path)
    args = parser.parse_args()

    # If file exists ignore this step
    if os.path.isfile(args.output_path):
        print("validate_repos: Cached")
        sys.exit(0)

    df = pd.read_csv(args.repos_csv)

    print("write_head_hashes: Started cloning repos and collecting head hashes")
    cpu_count = os.cpu_count() or 1
    processes_used = cpu_count - 2 if cpu_count > 3 else cpu_count
    with multiprocessing.Pool(processes=processes_used) as pool:
        result = list(
            tqdm(
                pool.imap(get_latest_hash, df.iterrows()),
                total=len(df),
            )
        )

    ## Introduce a new variable if the type changes.
    result_df = pd.DataFrame([i for i in result if i is not None])
    result_df = result_df.set_index(result_df.columns[0]).reset_index(drop=True)
    result_df.to_csv(args.output_path, index_label="idx")
    print("Finished Storing Repos Hashes")
