#!/usr/bin/env python3
"""Split the repos list according to the number of machine used."""

# usage: python3 get_repos.py --repos_path <repos_path>
#                               --machine_id <machine_id>
#                               --num_machines <num_machines>
#                               --output_path <output_path>
# This script splits the repos list for each machine and stores the local repos list.

import argparse
import pandas as pd
import numpy as np

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_path", type=str)
    parser.add_argument("--machine_id", type=int)
    parser.add_argument("--num_machines", type=int)
    parser.add_argument("--output_file", type=str)
    args = parser.parse_args()
    df = pd.read_csv(args.repos_path)
    # Make sure load factor is not biased
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    df = np.array_split(df, args.num_machines)[args.machine_id]

    df.to_csv(args.output_file, index=False)
    print("Number of local Repos:", len(df))
