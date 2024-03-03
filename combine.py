# -*- coding: utf-8 -*-
""" Combine two CSV files into a single CSV file. """
import pandas as pd

# Read the first CSV file
file1 = "input_data/repos_reaper_with_hashes.csv"
df1 = pd.read_csv(file1, index_col=0)
df1 = df1[["repository", "head hash"]]  # Keep only the 'repository' and 'hash' columns
print(df1.columns)
# Read the second CSV file
file2 = "input_data/repos_greatest_hits_with_hashes.csv"
df2 = pd.read_csv(file2, index_col=0)

# Store the original casing of repository names in df2
df2["repository_lower"] = df2["repository"].str.lower()

# Count the number of dropped entries from df2
num_dropped_entries = len(df2) - len(
    df2.drop_duplicates(subset="repository_lower", keep="first")
)

# Remove duplicates from df2
df2.drop_duplicates(subset="repository_lower", keep="first", inplace=True)

# Convert values to lowercase for case insensitivity
df1["repository"] = df1["repository"].str.lower()
df2.drop(
    columns=["repository_lower"], inplace=True
)  # Drop the temporary lowercase column

# Reset the index of both dataframes
df1.reset_index(drop=True, inplace=True)
df2.reset_index(drop=True, inplace=True)

# Concatenate both dataframes
combined_df = pd.concat([df1, df2], ignore_index=True)

# Add an 'idx' column
combined_df.reset_index(inplace=True, drop=True)

# Save the combined DataFrame to a new CSV file
output_file = "input_data/repos_combined_with_hashes.csv"

# Write the combined DataFrame to CSV without modifying the format
combined_df.to_csv(output_file, index_label="idx")

print(f"Combined DataFrame saved to {output_file}")
print(f"Number of dropped entries from df2: {num_dropped_entries}")
