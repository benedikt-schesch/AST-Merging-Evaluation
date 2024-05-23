# -*- coding: utf-8 -*-
"""Check for inconsistent results between merge tools and output them to a CSV.

usage: python3 check_inconsistencies.py --result_csv <path_to_result_csv> --output_csv <path_to_output_csv>

This script reads a result CSV file, checks for inconsistencies between merge tools based on fingerprints,
and writes the inconsistent results to a new CSV file.

Arguments:
- result_csv: path to the result CSV file
- output_csv: path to the output CSV file where inconsistent results will be saved
"""

import argparse
import pandas as pd
from typing import List


def check_fingerprint_consistency(
    result_df: pd.DataFrame, merge_tools: List[str]
) -> pd.DataFrame:
    """Check if the fingerprints are consistent and return inconsistent results.

    Args:
        result_df: DataFrame containing the results of the merge tools
        merge_tools: list of merge tools

    Returns:
        DataFrame with inconsistent results
    """
    inconsistencies = []

    for merge_tool1 in merge_tools:
        for merge_tool2 in merge_tools:
            if merge_tool1 != merge_tool2:
                # Check if fingerprints are the same
                same_fingerprint_mask = (
                    result_df[merge_tool1 + "_merge_fingerprint"]
                    == result_df[merge_tool2 + "_merge_fingerprint"]
                )

                # Check if results are the same
                same_result_mask = result_df[merge_tool1] == result_df[merge_tool2]

                # Check if the fingerprints are the same but the results are different
                inconsistent_mask = same_fingerprint_mask & ~same_result_mask
                if inconsistent_mask.sum() > 0:
                    inconsistent_results = result_df[inconsistent_mask].copy()
                    inconsistent_results["tool1"] = merge_tool1
                    inconsistent_results["tool2"] = merge_tool2
                    inconsistencies.append(result_df[inconsistent_mask])

    if inconsistencies:
        return pd.concat(inconsistencies).drop_duplicates()
    else:
        return pd.DataFrame()


def main():
    """Main function"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--result_csv",
        type=str,
        help="Path to the result CSV file",
        default="results/combined/result.csv",
    )
    parser.add_argument(
        "--output_csv",
        type=str,
        help="Path to the output CSV file for inconsistent results",
        default="results/combined/inconsistent_results.csv",
    )
    args = parser.parse_args()

    # Read the result CSV file
    result_df = pd.read_csv(args.result_csv, index_col="idx")

    # List of merge tools
    merge_tools = [
        col.split("_merge_fingerprint")[0]
        for col in result_df.columns
        if col.endswith("_merge_fingerprint")
    ]

    # Check for inconsistencies
    inconsistent_results = check_fingerprint_consistency(result_df, merge_tools)

    if not inconsistent_results.empty:
        # Write the inconsistent results to the output CSV file
        inconsistent_results.to_csv(args.output_csv, index_label="idx")
        print(f"Inconsistent results have been saved to {args.output_csv}")
        print("Number of inconsistencies found:", len(inconsistent_results))
    else:
        print("No inconsistencies found.")


if __name__ == "__main__":
    main()
