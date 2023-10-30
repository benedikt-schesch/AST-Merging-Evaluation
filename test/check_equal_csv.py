#!/usr/bin/env python3

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
        default="results-small",
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
        goal_df = pd.read_csv(goal_folder / goal_file, header=0, index_col="idx")
        actual_df = pd.read_csv(actual_file, header=0, index_col="idx")
        goal_df = remove_run_time(goal_df)
        actual_df = remove_run_time(actual_df)

        if not goal_df.equals(actual_df):
            # Print the differences.
            print(os.system(f"diff {goal_folder/goal_file} {actual_file}"))
            # Now print details, after diffs so it is not obscured by the diff output.
            different_columns = []
            for col in goal_df.columns:
                if "run_time" in col:
                    raise Exception(
                        f'goal_df.columns contains "run_time": {goal_df.columns}'
                    )
                if not col in actual_df:
                    print(f"Column {col} is not in actual_df")
                    print(goal_df[col])
                    different_columns.append(col)
                elif not goal_df[col].equals(actual_df[col]):
                    print(f"Column {col} is not equal.  Printing goal then actual.")
                    print(goal_df[col])
                    print(actual_df[col])
                    different_columns.append(col)
            print(
                f"{goal_folder / goal_file} and {actual_file} are not equal in columns:"
                + f" {different_columns}"
            )
            # Print the differences
            print(
                os.system(
                    f"diff {goal_folder/goal_file} {actual_file} in columns: {different_columns}"
                )
            )
            raise ValueError(f"{goal_folder/goal_file} and {actual_file} are not equal")
