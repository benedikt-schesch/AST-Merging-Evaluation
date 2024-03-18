#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Output a subset of the results that match a hard-coded condition, to a hard-coded file."""

import pandas as pd

df = pd.read_csv("../../results/combined/result.csv", index_col="idx")

# print(df.iloc[3])
# print(df.iloc[3].gitmerge_ort_imports_ignorespace)
# print(df.iloc[3].gitmerge_ort_ignorespace)
# print(
#     df.iloc[3].gitmerge_ort_imports_ignorespace == df.iloc[3].gitmerge_ort_ignorespace
# )


def is_success(val):
    """Returns true if the given result is a success result."""
    return val == "Tests_passed"


def merge_failed(val):
    """Returns true if the given result indicates that the merge succeeded."""
    return val == "Merge_failed"


def merge_succeeded(val):
    """Returns true if the given result indicates that the merge succeeded."""
    return val != "Merge_failed"


# Retain rows where gitmerge_ort_imports_ignorespace and gitmerge_ort_ignorespace differ.
# df = df[
#     merge_failed(df.gitmerge_ort_imports_ignorespace)
#     != merge_failed(df.gitmerge_ort_ignorespace)
# ]
# df.to_csv("../../results/combined/imports-differs-from-ort.csv", index_label="idx")

# Select some rows.
df = df[merge_failed(df.gitmerge_ort) != merge_failed(df.spork)]
# Select some columns (is it OK to omit "idx"??)
df = df[["gitmerge_ort", "spork"]]

df.to_csv("../../results/combined/spork-differs-from-ort.csv", index_label="idx")
