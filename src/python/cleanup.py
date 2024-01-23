# -*- coding: utf-8 -*-
""" Deletes empty folders in results/merges/"" """
from pathlib import Path
import pandas as pd

df = pd.read_csv("resultsrepos_head_passes.csv", index_col="idx")
base_path = "results/merges/"
counter = 0
for path in list(Path(base_path).glob("**")):
    # IF folder is empty delete it
    if not list(path.glob("*")):
        path.rmdir()
        print(path)
        counter += 1
print(counter)
