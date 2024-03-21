"""Recreates merges on all algorithms with a sample of commits.
"""

import os
from diff3_analysis import diff3_analysis

# Mixed conflict and pass examples from results_greatest_hits/result.csv
# Randomly chosen sample of mixed results from dataset
row_nums = [
    582,
    427,
    930,
    70,
    128,
    1444,
    1177,
    849,
    1425,
    1642,
    1897,
    862,
    943,
    1442,
    1120,
    111,
    693,
    535,
    354,
    530,
    845,
    654,
    921,
    464,
    1006,
    707,
    485,
    1928,
    809,
    1329,
    65,
    1890,
    100,
    247,
    2038,
    900,
]

# All merge tools
merge_tools = [
    "gitmerge_ort",
    "gitmerge_ort_adjacent",
    "gitmerge_ort_ignorespace",
    "gitmerge_ort_imports",
    "gitmerge_ort_imports_ignorespace",
    "gitmerge_resolve",
    "gitmerge_recursive_histogram",
    "gitmerge_recursive_ignorespace",
    "gitmerge_recursive_minimal",
    "gitmerge_recursive_myers",
    "gitmerge_recursive_patience",
    "git_hires_merge",
    "spork",
    "intellimerge",
]


def run_analysis():
    """
    Analyzes merge conflicts on a sample of repos with all merge algorithms.

    Returns:
        None
    """

    # Ensure the base output directory exists
    base_output_dir = "./merge_conflict_analysis_diffs"

    # Loop through each conflict, recreating merges to repo_output_dir
    for row_num in row_nums:
        for merge_tool in merge_tools:
            # Create a subdirectory for this specific results_index
            repo_output_dir = os.path.join(base_output_dir, str(row_num), merge_tool)
            os.makedirs(repo_output_dir, exist_ok=True)
            diff3_analysis(merge_tool, row_num, repo_output_dir)
