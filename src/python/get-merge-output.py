#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Given an index and tool, creates the merge for that index and tool.
# The output appears in ... .

import argparse
import os
import pandas as pd
import shutil
import subprocess

from git import Repo
from pathlib import Path


CLONE_ROOT = "/scratch/mernst/ast-merging-clones/"
if not Path(CLONE_ROOT).is_dir():
    os.makdirs(CLONE_ROOT)

parser = argparse.ArgumentParser("get-merge-output")
parser.add_argument(
    "index", help="The index of the row whose merge to recreate.", type=int
)
parser.add_argument("tool", help="The name of the merge tool to use.", type=str)
args = parser.parse_args()

df = pd.read_csv("../../results/combined/result.csv", index_col="idx")

row = df.iloc[args.index]

slug = row["repository"]
print(slug)
left_sha = row["left"]
right_sha = row["right"]

slug_split = slug.split("/")
repo_org = slug_split[0]
repo_name = slug_split[1]

clone_parent_dir_name = CLONE_ROOT + slug + "/" + row["merge"] + "/" + args.tool
clone_parent_dir = Path(clone_parent_dir_name)
if not clone_parent_dir.is_dir():
    os.makedirs(clone_parent_dir)
print("clone_parent_dir", clone_parent_dir)
clone_dir_name = clone_parent_dir_name + "/" + repo_name
clone_dir = Path(clone_dir_name)


if clone_dir.is_dir():
    shutil.rmtree(clone_dir)

clone_repo = Repo.clone_from("https://github.com/" + slug + ".git", clone_dir)
clone_repo.git.checkout(row["branch_name"])

clone_repo.git.checkout(left_sha)
clone_repo.git.checkout("-b", "left-branch-for-merge")
clone_repo.git.checkout(right_sha)
clone_repo.git.checkout("-b", "right-branch-for-merge")

subprocess.run(
    [
        "../scripts/merge_tools/" + args.tool + ".sh",
        clone_dir,
        "left-branch-for-merge",
        "right-branch-for-merge",
    ]
)
