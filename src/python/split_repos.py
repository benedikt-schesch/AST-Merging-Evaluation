#!/usr/bin/env python3
"""Split the repos list according to the number of machines used.

usage: python3 get_repos.py --repos_csv <path_to_repos.csv>
                            --machine_id <machine_id>
                            --num_machines <num_machines>
                            --output_file <output_path>
This script splits the repos list for each machine and stores the local repos list.
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_csv", type=Path)
    parser.add_argument("--machine_id", type=int)
    parser.add_argument("--num_machines", type=int)
    parser.add_argument("--output_file", type=Path)
    args = parser.parse_args()
    df: pd.DataFrame = pd.read_csv(args.repos_csv, index_col="idx")
    # Make sure load factor is not biased
    df = df.sample(frac=1, random_state=42)
    df = np.array_split(df, args.num_machines)[args.machine_id]
    df.sort_index(inplace=True)

    df.to_csv(args.output_file, index_label="idx")
    print("Number of local repos in", args.repos_csv, "=", len(df))
