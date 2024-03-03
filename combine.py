# -*- coding: utf-8 -*-
"""Combine the contents of two CSV files into a single CSV file."""
import pandas as pd

# Read the first CSV file
file1 = "input_data/repos_reaper.csv"
df1 = pd.read_csv(file1, index_col=0)
if "head hash" in df1.columns:
    df1 = df1[
        ["repository", "head hash"]
    ]  # Keep only the 'repository' and 'hash' columns
else:
    df1 = df1[["repository"]]

# Read the second CSV file
file2 = "input_data/repos_greatest_hits.csv"
df2 = pd.read_csv(file2, index_col=0)

# Reset the index of both dataframes
df1.reset_index(drop=True, inplace=True)
df2.reset_index(drop=True, inplace=True)

# Concatenate both dataframes
combined_df = pd.concat([df1, df2], ignore_index=True)

# Add an 'idx' column
combined_df.reset_index(inplace=True, drop=True)

# Save the combined DataFrame to a new CSV file
output_file = "input_data/repos_combined.csv"

# Write the combined DataFrame to CSV without modifying the format
combined_df.to_csv(output_file, index_label="idx")

print(f"Combined DataFrame saved to {output_file}")
