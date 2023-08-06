#!/usr/bin/env python3

"""Remove all columns whose name contains "run_time"."""

import pandas as pd
from argparse import ArgumentParser

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--input",
        type=str,
        default="results-small/result.csv",
        help="Path to CSV file with run time columns",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results-small/result-without-times.csv",
        help="Path to CSV file without run time columns",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    df = df.loc[:, ~df.columns.str.contains("run_time")]
    df.to_csv(args.output, index=False)
