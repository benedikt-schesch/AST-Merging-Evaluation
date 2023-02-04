#!/usr/bin/env python3

import pandas as pd

df = pd.read_csv("data/result.csv")


for i in ["git merge", "spork", "intellimerge"]:
    for j in df[i].unique():
        instances = sum(df[i] == j)
        print(i, j, instances)
