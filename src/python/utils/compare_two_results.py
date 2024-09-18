#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""Output indices where the differences of two columns are different between two result files (CSV).

Params:
    input1: str - The first input file path.
    input1-column1: str - The first column name in the first input file.
    input1-column2: str - The second column name in the first input file.
    input2: str - The second input file path.
    input2-column1: str - The first column name in the second input file.
    input2-column2: str - The second column name in the second input file.

Prints the results to standard out.
"""

import argparse
import pandas as pd


def main():
    "Selects rows and columns from results."
    parser = argparse.ArgumentParser(
        prog="select_from_results.py",
        description="Outputs a subset of the results, to standard out",
    )
    parser.add_argument(
        "--input1",
        action="store",
        default="results/combined/result.csv",
    )
    parser.add_argument("--input1-column1", action="store", default="gitmerge_ort")
    parser.add_argument("--input1-column2", action="store", default="ivn")
    parser.add_argument(
        "--input2",
        action="store",
        default="results/combined/result_346.csv",
    )
    parser.add_argument("--input2-column1", action="store", default="gitmerge_ort")
    parser.add_argument("--input2-column2", action="store", default="plumelib_ort")
    args = parser.parse_args()

    # Read files and set idx as index.
    df1 = pd.read_csv(args.input1).set_index("idx")
    df2 = pd.read_csv(args.input2).set_index("idx")

    # Loop through each row.
    for (index1, row1), (index2, row2) in zip(df1.iterrows(), df2.iterrows()):
        # Boolean of the two columns.
        input1_bool = row1[args.input1_column1] == row1[args.input1_column2]
        input2_bool = row2[args.input2_column1] == row2[args.input2_column2]

        # If the two booleans are different, print the row.
        if input1_bool != input2_bool:
            print(
                f"Idx: {index1}    {args.input1_column1}: {row1[args.input1_column1]}, {args.input1_column2}: {row1[args.input1_column2]} | {args.input2_column1}: {row2[args.input2_column1]}, {args.input2_column2}: {row2[args.input2_column2]}"
            )


if __name__ == "__main__":
    main()
