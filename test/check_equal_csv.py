#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Compare all csv files except for the run_time columns."""

import os
from argparse import ArgumentParser
from pathlib import Path
import pandas as pd


def remove_run_time(df):
    """Remove all columns whose name contains "run_time"."""
    df = df.drop(columns=[c for c in df.columns if "run_time" in c])
    return df


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--actual_folder",
        type=str,
        help="Path to actual folder",
        default="results/small",
    )
    parser.add_argument(
        "--goal_folder",
        type=str,
        help="Path to the folder with goal files",
        default="test/small-goal-files",
    )
    args = parser.parse_args()

    goal_folder = Path(args.goal_folder)
    actual_folder = Path(args.actual_folder)

    for goal_file in goal_folder.glob("**/*.csv"):
        goal_file = goal_file.relative_to(goal_folder)
        print(f"Checking {goal_file}")
        actual_file = actual_folder / goal_file
        assert actual_file.exists(), f"{actual_file} does not exist"
        try:
            goal_df = pd.read_csv(goal_folder / goal_file, header=0, index_col="idx")
        except Exception:
            goal_df = pd.read_csv(goal_folder / goal_file)
            actual_df = pd.read_csv(actual_file)
            if not goal_df.equals(actual_df):
                print(f"{goal_folder/goal_file} and {actual_file} are not equal")
                print("Goal file:")
                print(goal_df)
                print("Actual file:")
                print(actual_df)
                raise ValueError(
                    f"{goal_folder/goal_file} and {actual_file} are not equal"
                )
            continue
        actual_df = pd.read_csv(actual_file, header=0, index_col="idx")
        goal_df = remove_run_time(goal_df)
        actual_df = remove_run_time(actual_df)

        different_columns = []
        all_columns = set(goal_df.columns) | set(actual_df.columns)
        for col in all_columns:
            if "intellimerge" in col or "run_time" in col or "resolve" in col:
                continue
            if col not in goal_df:
                print(f"Column {col} is in actual_df but not in goal_df")
                different_columns.append(col)
            elif col not in actual_df:
                print(f"Column {col} is in goal_df but not in actual_df")
                different_columns.append(col)
            elif not goal_df[col].equals(actual_df[col]):
                print(f"Column {col} is not equal")
                different_columns.append(col)

        if len(different_columns) > 0:
            print(f"Columns that are not equal: {different_columns}")
            print(f"{goal_folder/goal_file} and {actual_file} are not equal")
            raise ValueError("goal_df and actual_df have different columns or values")

        for col in goal_df.columns:
            if "intellimerge" in col or "resolve" in col:
                continue
            # Check if the columns are equal
            if actual_df[col].equals(goal_df[col]):
                continue
            # Print the differences.
            diff_exit_code = os.waitstatus_to_exitcode(
                os.system(f"diff {goal_folder/goal_file} {actual_file}")
            )
            print(f"diff exit code: {diff_exit_code}")
            # Now print details, after diffs so it is not obscured by the diff output.
            different_columns = []
            for col in goal_df.columns:
                if "run_time" in col:
                    raise ValueError(
                        f'goal_df.columns contains "run_time": {goal_df.columns}'
                    )
                if col not in actual_df:
                    print(f"Column {col} is not in actual_df")
                    print(goal_df[col])
                    different_columns.append(col)
                elif not goal_df[col].equals(actual_df[col]):
                    print(f"Column {col} is not equal.  Printing goal then actual.")
                    print(goal_df[col])
                    print(actual_df[col])
                    different_columns.append(col)
            print(
                f"{goal_folder / goal_file} and {actual_file} are not equal in columns: "
                + f"{different_columns}"
            )
            # Print the differences
            print(os.system(f"diff -u {goal_folder/goal_file} {actual_file}"))
            raise ValueError(f"{goal_folder/goal_file} and {actual_file} are not equal")
