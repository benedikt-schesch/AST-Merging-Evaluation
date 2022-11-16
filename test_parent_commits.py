import pandas as pd
import git
import subprocess
import shutil
import os
import multiprocessing
import time
from pebble import ProcessPool

if __name__ == '__main__':
    pwd = os.getcwd()
    df = pd.read_csv("valid_repos.csv")

    for idx,row in df.iterrows():
        repo_name = row["repository"]
        merge_list_file = "merges/"+repo_name.split("/")[1]+".csv"
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(merge_list_file,names=["merge","left","right","base"])

        if len(merges) > 20:
            continue

        repo_dir = "repos/"+repo_name
        merges["repo"] = [1 for i in merges.iterrows()]

        if not os.path.isdir(repo_dir):
            git_url = "https://github.com/"+repo_name+".git"
            repo = git.Repo.clone_from(git_url, repo_dir)
        else:
            repo = git.Git(repo_dir)
        repo.fetch()

        for idx2, row2 in merges.iterrows():
            #Git Merge
            repo.checkout(row2["left"])
            test1 = subprocess.run([pwd+"/tester.sh",repo_dir]).returncode
            repo.checkout(row2["right"])
            test2 = subprocess.run([pwd+"/tester.sh",repo_dir]).returncode
            if test1 == 0 and test2 == 0:
                merges["repo"][idx2] = 0
        merges.to_csv(merge_list_file,header=False)
