#!/usr/bin/env python3
"""Store the hash of the HEAD of main branch for each repository enabling reproducible results.

usage: python3 write_head_hashes.py --repos_csv <repos.csv>
                                    --output_path <valid_repos.csv>

Input: a csv of repos.
The input file `repos.csv` must contain a header, one of whose columns is "repository".
That column contains "ORGANIZATION/REPO" for a GitHub repository.
Output: the hash of the HEAD of the main branch used for reproducible results.
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
        sys.exit(0)

    df = pd.read_csv(args.repos_csv)

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

    result = pd.DataFrame([i for i in result if i is not None])
    result = result.set_index(result.columns[0]).reset_index(drop=True)
    result.to_csv(args.output_path)
    print("Finished Storing Repos Hashes")
