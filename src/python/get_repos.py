#!/usr/bin/env python3
"""Download repo list."""

# usage: python3 get_repos.py

# This script first downloads the reaper dataset.  It then outputs, to file data/repos.csv, the Java
# repos with more than 10 GitHub stars and a unit_test score of more than 0.25.

import gzip
import urllib.request
from io import BytesIO
import os
import sys

import pandas as pd
import numpy as np

repos_csv = "data/repos.csv"

if __name__ == "__main__":
    if os.path.isfile(repos_csv):
        print("get_repos.py:", repos_csv, "exists; exiting.")
        sys.exit(0)

    urllib.request.urlretrieve(
        "https://reporeapers.github.io/static/downloads/dataset.csv.gz",
        "data/repos.csv.gz",
    )
    with gzip.open("data/repos.csv.gz", "rb") as f:
        file_content = f.read()

    df = pd.read_csv(BytesIO(file_content))
    df = df[df["language"] == "Java"]
    df = df.replace(to_replace="None", value=np.nan).dropna()
    df = df[df["stars"].astype(int) > 10]
    df = df[df["unit_test"] > 0.25]

    df.to_csv(repos_csv)

    print("Number of Repos written to", repos_csv, ":", len(df))
