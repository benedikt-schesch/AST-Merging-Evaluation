# -*- coding: utf-8 -*-
"""Delete the keys containing 'imports' in the JSON files in the given directory."""

import pandas as pd
from pathlib import Path
from argparse import ArgumentParser
import json
from repo import MERGE_TOOL


def delete_row(row):
    """Main function."""
    repo_name = row["repository"]
    entries_deleted = 0
    sha_cache = Path("cache/sha_cache_entry/" + repo_name + ".json")
    with open(sha_cache, "r", encoding="utf-8") as file:
        data = json.load(file)
    sha_to_del = set()
    for merge_tool in MERGE_TOOL:
        if merge_tool == MERGE_TOOL.intellimerge:
            continue
        sha_to_del.add(row[merge_tool.name + "_merge_fingerprint"])
    test_cache = Path("cache/test_cache/" + repo_name + ".json")
    with open(test_cache, "r", encoding="utf-8") as file:
        data = json.load(file)
    for sha in sha_to_del:
        if sha in data:
            del data[sha]
            entries_deleted += 1
    with open(test_cache, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)
    print(f"Number of entires deleted: {entries_deleted}")
    print(f"Total rows: {len(df)}")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--result",
        type=str,
        default="results/combined/result.csv",
        help="The result csv file.",
    )
    parser.add_argument(
        "--idx",
        type=str,
        required=True,
        help="The indices of the rows whose test results should be deleted from cache, separated by commas.",
    )
    args = parser.parse_args()
    idx_list = str(args.idx).split(",")
    df = pd.read_csv(args.result, index_col="idx")
    for idx in idx_list:
        row = df.loc[idx]
        delete_row(row)
