#!/usr/bin/env python3
"""Download repo list."""

# usage: python3 get_repos.py
# This script downloads the reaper dataset and only keeps repos with
# at least 10 GitHub stars and a unit_test score of at least 0.25

import gzip
import urllib.request
from io import BytesIO

import pandas as pd
import numpy as np

if __name__ == "__main__":
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

    df.to_csv("data/repos.csv")

    print("Number of Repos:", len(df))
