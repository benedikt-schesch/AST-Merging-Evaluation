#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Output a subset of the results, to standard out.
The arguments are a query and an optional list of columns.
It is also permitted to pass "--input CSV_FILENAME".
The query is executed (to select rows), then columns are output that include:
 * idx
 * all the columns that appear in the query
 * any additional columns specified on the command line.

The query is an expression using dataframe variables.

Here are example invocations:
  select_from_results.py '(gitmerge_ort == "Merge_failed") and (spork != "Merge_failed")'
  select_from_results.py '(gitmerge_ort == "Merge_failed") != (spork == "Merge_failed")'

The resulting .csv is useful for manual examination but cannot be passed to
`replay_merge.py` because that requires a .csv file with all tools and all
fingerprints.
"""

import argparse
from os import system
import re
import tempfile
import pandas as pd


def columns_in_query(query):
    """Returns all the identifiers used in the query."""
    result = re.findall(r"""(?<!['"])\b[A-Za-z][A-Za-z_]*\b(?!['"])""", query)
    while "and" in result:
        result.remove("and")
    while "or" in result:
        result.remove("or")
    return result


# Testing:
# columns_in_query('(gitmerge_ort == "Merge_failed") && (spork != "Merge_failed")')
# columns_in_query('(gitmerge_ort == "Merge_failed") != (spork == "Merge_failed")')


def main():
    "Selects rows and columns from results."
    parser = argparse.ArgumentParser(
        prog="select_from_results.py",
        description="Outputs a subset of the results, to standard out",
    )
    parser.add_argument("query")
    parser.add_argument(
        "--input",
        action="store",
        default="results/combined/result_adjusted.csv",
    )
    parser.add_argument("columns", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    df = pd.read_csv(args.input)

    # Select some rows.
    df = df.query(args.query)

    # Select some columns
    columns_to_select = (
        [
            "idx",
            "repo-idx",
            "merge-idx",
            "branch_name",
            "merge",
            "left",
            "left_tree_fingerprint",
            "right",
            "right_tree_fingerprint",
        ]
        + columns_in_query(args.query)
        + args.columns
        + ["repository"]
    )
    df = df[columns_to_select]

    # Gross way to produce output to standard out
    with tempfile.NamedTemporaryFile() as tmpfile:
        df.to_csv(tmpfile)
        system("cat " + tmpfile.name)


if __name__ == "__main__":
    main()
