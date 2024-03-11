#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd

df = pd.read_csv("../../results/combined/result.csv", index_col="idx")

# print(df.iloc[3])
# print(df.iloc[3].gitmerge_ort_imports_ignorespace)
# print(df.iloc[3].gitmerge_ort_ignorespace)
# print(
#     df.iloc[3].gitmerge_ort_imports_ignorespace == df.iloc[3].gitmerge_ort_ignorespace
# )


def is_success(val):
    return val == "Tests_passed"


# Retain rows where gitmerge_ort_imports_ignorespace and gitmerge_ort_ignorespace differ.
df = df[
    is_success(df.gitmerge_ort_imports_ignorespace)
    != is_success(df.gitmerge_ort_ignorespace)
]

df = df.to_csv("../../results/combined/imports-differs-from-ort.csv", index_label="idx")
