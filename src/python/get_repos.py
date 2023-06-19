#!/usr/bin/env python3
"""Download repo list."""

# usage: python3 get_repos.py

# This script creates file input_data/repos.csv from part of the reaper dataset:
# the Java repos with more than 10 GitHub stars and a unit_test score of more than 0.25.
# This script only needs to be re-run when you desire to re-create that file (which is rare).

import gzip
import urllib.request
from io import BytesIO
import os
import sys

import pandas as pd
import numpy as np

repos_csv = "input_data/repos.csv"

if __name__ == "__main__":
    urllib.request.urlretrieve(
        "https://reporeapers.github.io/static/downloads/dataset.csv.gz",
        "data/repos.csv.gz",
    )
    with gzip.open("data/repos.csv.gz", "rb") as f:
        df = pd.read_csv(BytesIO(f.read()))

    df = df[df["language"] == "Java"]
    df = df.replace(to_replace="None", value=np.nan).dropna()
    df = df[df["stars"].astype(int) > 10]
    df = df[df["unit_test"] > 0.25]

    df.to_csv(repos_csv)

    print("Number of repos written to", repos_csv, ":", len(df))
