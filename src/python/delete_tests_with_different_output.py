# -*- coding: utf-8 -*-
"""Delete the keys containing 'imports' in the JSON files in the given directory."""

import pandas as pd
from pathlib import Path
from argparse import ArgumentParser
from repo import MERGE_TOOL, TEST_STATE
import json


def main():
    """Main function."""
    parser = ArgumentParser()
    parser.add_argument(
        "--result",
        type=str,
        default="results/combined/result.csv",
        help="The result csv file.",
    )
    rows_affected = 0
    entries_deleted = 0
    args = parser.parse_args()
    df = pd.read_csv(Path(args.result))
    for _, row in df.iterrows():
        failed_tests_count = len(
            [
                row[merge_tool.name]
                for merge_tool in MERGE_TOOL
                if merge_tool != MERGE_TOOL.intellimerge
                and row[merge_tool.name] == TEST_STATE.Tests_failed.name
            ]
        )
        successful_tests_count = len(
            [
                row[merge_tool.name]
                for merge_tool in MERGE_TOOL
                if merge_tool != MERGE_TOOL.intellimerge
                and row[merge_tool.name] == TEST_STATE.Tests_passed.name
            ]
        )
        if failed_tests_count > 0 and successful_tests_count > 0:
            rows_affected += 1
            repo_name = row["repository"]
            sha_cache = Path("cache/sha_cache_entry/" + repo_name + ".json")
            with open(sha_cache, "r", encoding="utf-8") as file:
                data = json.load(file)
            sha_to_del = []
            for merge_tool in MERGE_TOOL:
                if merge_tool == MERGE_TOOL.intellimerge:
                    continue
                if (
                    row[merge_tool.name] == TEST_STATE.Tests_failed.name
                    or row[merge_tool.name] == TEST_STATE.Tests_passed.name
                ):
                    cache_entry = (
                        row["left"] + "_" + row["right"] + "_" + merge_tool.name
                    )
                    # assert data[row["right"]+"_"+row["left"]+"_"+merge_tool.name]["sha"] == row[merge_tool.name+"_merge_fingerprint"]
                    sha_to_del.append(data[cache_entry]["sha"])
            test_cache = Path("cache/test_cache/" + repo_name + ".json")
            with open(test_cache, "r", encoding="utf-8") as file:
                data = json.load(file)
            for sha in sha_to_del:
                del data[sha]
                entries_deleted += 1
            # with open(test_cache, "w", encoding="utf-8") as file:
            #     json.dump(data, file, indent=4)
            print(f"Deleting {sha_to_del} from {sha_cache}")
    print(f"Rows affected: {rows_affected}")
    print(f"Entries deleted: {entries_deleted}")
    print(f"Total rows: {len(df)}")


if __name__ == "__main__":
    main()
