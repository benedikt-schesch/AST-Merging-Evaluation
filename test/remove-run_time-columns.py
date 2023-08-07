#!/usr/bin/env python3

"""Remove all columns whose name contains "run_time"."""

from argparse import ArgumentParser
import pandas as pd

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--input",
        type=str,
        help='Path to CSV file with "run_time" columns',
    )
    parser.add_argument(
        "--output",
        type=str,
        help='Path to CSV file without "run_time" columns',
    )
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    df = df.drop(columns=[c for c in df.columns if "run_time" in c])
    df.to_csv(args.output, index=False)
