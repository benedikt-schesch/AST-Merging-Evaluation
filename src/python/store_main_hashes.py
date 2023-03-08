#!/usr/bin/env python3
"""Store the hash of the HEAD of main branch for each repository enabling reproducible results."""

# usage: python3 store_main_hashes.py --repos_path <repos.csv>
#                                     --output_path <valid_repos.csv>
#
# This script takes a csv of repos.
# It stores the hash of the HEAD of the main branch used for reproducible results.
# The input file `repos.csv` must contain a header, one of whose columns is "repository".
# That column contains "ORGANIZATION/REPO" for a GitHub repository.
# Output file is found in output_path

import os
import sys
import argparse
from pathlib import Path
from validate_repos import get_repo

from tqdm import tqdm
import pandas as pd

if __name__ == "__main__":
    Path("repos").mkdir(parents=True, exist_ok=True)

    print("Started Storing Repos Hashes")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_path", type=str)
    parser.add_argument("--output_path", type=str)
    args = parser.parse_args()

    # If file exists ignore this step
    if os.path.isfile(args.output_path):
        sys.exit(0)

    df = pd.read_csv(args.repos_path)
    result = []

    for idx, row in tqdm(df.iterrows(), total=len(df)):
        repo_name = row["repository"]
        print(repo_name, ": Started")

        try:
            print(repo_name, ": Cloning repo")
            repo = get_repo(repo_name)
        except Exception:
            print(repo_name, ": Finished testing, result = exception")
            continue
        row["Validation hash"] = repo.head.commit.hexsha
        result.append(row)

    result = pd.DataFrame(result)
    result = result.set_index(result.columns[0]).reset_index(drop=True)
    result.to_csv(args.output_path)
    print("Finished Storing Repos Hashes")
