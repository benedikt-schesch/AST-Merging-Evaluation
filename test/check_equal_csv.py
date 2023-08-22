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
        "--test_folder", type=str, help="Path to test folder", default="results-small"
    )
    parser.add_argument(
        "--target_folder",
        type=str,
        help="Path to the folder with target files",
        default="test/small-goal-files",
    )
    args = parser.parse_args()

    target_folder = Path(args.target_folder)
    test_folder = Path(args.test_folder)

    for target_file in target_folder.glob("**/*.csv"):
        target_file = target_file.relative_to(target_folder)
        print(f"Checking {target_file}")
        test_file = test_folder / target_file
        assert test_file.exists(), f"{test_file} does not exist"
        target_df = pd.read_csv(target_folder / target_file, header=0, index_col="idx")
        test_df = pd.read_csv(test_file, header=0, index_col="idx")
        target_df = remove_run_time(target_df)
        test_df = remove_run_time(test_df)

        if not target_df.equals(test_df):
            for col in target_df.columns:
                if not target_df[col].equals(test_df[col]):
                    print(f"Column {col} is not equal")
                    print(target_df[col])
                    print(test_df[col])
            print(f"{target_file} and {test_file} are not equal")
            # Print the differences
            print(os.system(f"diff {target_folder/  target_file} {test_file}"))
            raise ValueError(f"{target_file} and {test_file} are not equal")
