#!/usr/bin/env python3
"""Write the hash of the HEAD of the default branch (often "main" or "master") for each repository to its own file.
If the file already exists, do nothing.
After this is done, the resulting files are used indefinitely, for reproducible results.

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
from validate_repos import clone_repo
from tqdm import tqdm
import pandas as pd


def get_latest_hash(args):
    ## TODO: Testing isn't mentioned in the file documentation, and I don't see
    ## where in this file testing is performed.
    """Checks if the head of main passes test.
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
    parser.add_argument("--repos_csv", type=str)
    parser.add_argument("--output_path", type=str)
    args = parser.parse_args()

    # If file exists ignore this step
    if os.path.isfile(args.output_path):
        print("validate_repos: Cached")
        sys.exit(0)

    df = pd.read_csv(args.repos_csv)

    ## TODO: What is being tested?
    print("validate_repos: Started Testing")
    cpu_count = os.cpu_count() or 1
    processes_used = cpu_count - 2 if cpu_count > 3 else cpu_count
    with multiprocessing.Pool(processes=processes_used) as pool:
        result = list(
            tqdm(
                pool.imap(get_latest_hash, df.iterrows()),
                total=len(df),
            )
        )

    ## TODO: It is confusing to reassign a veriable with a different type.
    ## Introduce a new variable if the type changes.
    result = pd.DataFrame([i for i in result if i is not None])
    result = result.set_index(result.columns[0]).reset_index(drop=True)
    result.to_csv(args.output_path)
    print("Finished Storing Repos Hashes")
