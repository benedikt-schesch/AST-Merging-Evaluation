#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pandas as pd
from pathlib import Path

# -------------------------------
# Parameters – adjust as needed
# -------------------------------
n = 50  # Number of samples; change as needed
random_seed = 42  # Fixed seed for deterministic shuffling

# File and folder paths:
adjusted_csv_path = Path("results/combined/result_adjusted.csv")
repos_combined_path = Path("input_data/repos_combined.csv")
sampled_repos_out_path = Path(f"input_data/repos_combined_sampled_{n}.csv")
merges_base_dir = Path("results/combined/merges")
merges_sampled_dir = Path(f"results/combined_sampled_{n}/merges")

# -------------------------------
# STEP 1: Sample n failed git ort merges using pandas
# -------------------------------
# Load the adjusted CSV.
result_df = pd.read_csv(adjusted_csv_path)

# Filter for rows where git merge ort failed.
failed_df = result_df[result_df["gitmerge_ort"] == "Merge_failed"]
print(f"Found {len(failed_df)} failed git ort merges in total.")

# Shuffle deterministically and sample n rows. Use .copy() to avoid SettingWithCopyWarning.
sampled_df = failed_df.sample(frac=1, random_state=random_seed).iloc[:n].copy()

# Extract merge commit hashes and repository names.
sampled_merge_hashes = set(sampled_df["merge"])
sampled_repos = set(sampled_df["repository"])
print(f"Sampling {len(sampled_df)} merges from {len(sampled_repos)} repositories.")

# -------------------------------
# STEP 2: Create a repos file for the sampled repositories
# -------------------------------
# Load and filter the full repositories list.
repos_df = pd.read_csv(repos_combined_path)
sampled_repos_df = repos_df[repos_df["repository"].isin(sampled_repos)]

# Write the filtered repositories to a new CSV.
sampled_repos_df.to_csv(sampled_repos_out_path, index=False)
print(f"Wrote {len(sampled_repos_df)} repository rows to {sampled_repos_out_path}")

# -------------------------------
# STEP 3: Prepare and write merge CSV files for each sampled repository
# -------------------------------
# Ensure the output directory exists.
merges_sampled_dir.mkdir(parents=True, exist_ok=True)

# Modify the sampled DataFrame:
#   - Drop the existing 'idx' column.
#   - Rename columns: "merge" -> "merge_commit", "left" -> "parent_1",
#     "right" -> "parent_2", and "merge-idx" -> "idx".
#   - Reorder the columns.
sampled_df.drop(columns=["idx"], inplace=True)
sampled_df.rename(
    columns={
        "merge": "merge_commit",
        "left": "parent_1",
        "right": "parent_2",
        "merge-idx": "idx",
    },
    inplace=True,
)
columns_order = [
    "idx",
    "branch_name",
    "merge_commit",
    "parent_1",
    "parent_2",
    "notes",
    "repository",
]
sampled_df = sampled_df[columns_order]

# For each sampled repository, write its merges to a CSV file.
for repo in sampled_repos:
    repo_df = sampled_df[sampled_df["repository"] == repo]
    # Remove the 'repository' column.
    repo_df.drop(columns=["repository"], inplace=True)
    output_path = merges_sampled_dir / f"{repo}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    repo_df.to_csv(output_path, index=False)
    print(f"Wrote {len(repo_df)} merge rows for repository '{repo}' to {output_path}")

print("Sampling complete!")
