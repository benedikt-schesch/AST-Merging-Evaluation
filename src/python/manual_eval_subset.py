#!/usr/bin/env python3

import pandas as pd
import os
import git
import shutil
import subprocess

def merge(merging_method,left,right,base_dir):
    repo_dir = base_dir+"/repo"
    repo_dir_copy = base_dir+"/"+merging_method

    shutil.copytree(repo_dir, repo_dir_copy+"/"+merging_method)
    repo = git.Git(repo_dir_copy+"/"+merging_method)
    repo.fetch()
    repo.checkout(left)
    repo.checkout('-b','AOFKMAFNASFKJNRFQJXNFHJ1')
    repo.checkout(right)
    repo.checkout('-b','AOFKMAFNASFKJNRFQJXNFHJ2')
    subprocess.run(["src/scripts/merge_tools/"+merging_method+".sh",
                        repo_dir_copy+"/"+merging_method,
                        "AOFKMAFNASFKJNRFQJXNFHJ1",
                        "AOFKMAFNASFKJNRFQJXNFHJ2"])


SCRATCH_DIR = "/scratch/scheschb/AST-Merging-Evaluation/scratch/"

df = pd.read_csv("data/result-5.csv",index_col=0)

merging_methods = ["git merge","spork","intellimerge"]
repo_dir = "../AST_repos/"

conflicts = []
for idx, row in df.iterrows():
    conflict = False
    for method1 in merging_methods:
        for method2 in merging_methods:
            if row[method1] != row[method2] and row[method1] < 100 and row[method2] < 100:
                conflict = True
    if conflict:
        conflicts.append(row)

conflicts = pd.DataFrame(conflicts)
conflicts = conflicts.sample(n=25,random_state=42)
conflicts.to_csv("data/manual_review.csv")

for i in range(25):
    row = conflicts.iloc[i]
    repo_name = row["project name"]
    base_dir = "../AST_repos/"+str(i)
    if os.path.isdir(base_dir):
        shutil.rmtree(base_dir)
    os.mkdir(base_dir)
    repo_dir = base_dir+"/repo"
    git_url = "https://github.com/"+repo_name+".git"
    repo = git.Repo.clone_from(git_url, repo_dir)
    repo.remote().fetch()


    merge("gitmerge",row["left"],row["right"],base_dir)
    merge("intellimerge",row["left"],row["right"],base_dir)
    merge("spork",row["left"],row["right"],base_dir)
    # repo_name = row["project name"]
    # left = row["left"]
    # right = row["right"]
    # base = row["base"]

    # for merging_method in ["gitmerge","spork","intellimerge"]:
    #     dst_name = SCRATCH_DIR+repo_name+"_"+left+"_"+right+"_"+base+"_"+merging_method
    #     subprocess.run(["rsync","-rauL","scheschb@bicycle.cs.washington.edu:"+dst_name,base_dir])
    # shutil.copytree(repo_dir_copy+"/"+merging_method,dst_name)
    
