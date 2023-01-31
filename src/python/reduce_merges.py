#!/usr/bin/env python3

import os
import pandas as pd
import argparse
import shutil

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--merges_path",type=str)
    parser.add_argument("--output_dir",type=str)
    parser.add_argument("--max_merges",type=int)
    args = parser.parse_args()

    if os.path.isdir(args.output_dir):
        shutil.rmtree(args.output_dir)
    os.mkdir(args.output_dir)

    for file in os.listdir(args.merges_path):
        df = pd.read_csv(args.merges_path+file)
        if len(df) > args.max_merges:
            df = df.sample(n=args.max_merges,random_state=42)
        df.to_csv(args.output_dir+file)
