import pandas as pd
import git
import subprocess
import shutil
import os
import multiprocessing
import time
from pebble import ProcessPool

def pass_test(args):
    repo_name,commit,working_dir,cache = args
    cache_file = cache+repo_name.split("/")[1]+"_"+commit

    if os.path.isfile(cache_file):
        with open(cache_file) as f:
            return int(next(f))
    
    process = multiprocessing.current_process()
    pid = str(process.pid)

    repo_dir = "repos/"+repo_name
    pwd = os.getcwd()
    repo_dir_copy = pwd+working_dir+pid
    
    if not os.path.isdir(repo_dir):
        git_url = "https://github.com/"+repo_name+".git"
        repo = git.Repo.clone_from(git_url, repo_dir)
    else:
        repo = git.Git(repo_dir)
    repo.fetch()
    

    if os.path.isdir(repo_dir_copy):
        shutil.rmtree(repo_dir_copy)
    shutil.copytree(repo_dir, repo_dir_copy)
    repo = git.Git(repo_dir_copy)
    repo.fetch()
    repo.checkout(commit)
    try:
        test = subprocess.run([pwd+"/src/scripts/tester.sh",repo_dir_copy]).returncode
        with open(cache_file,"w") as f:
            f.write(str(test))
        shutil.rmtree(repo_dir_copy)
        return test
    except Exception:
        with open(cache_file,"w") as f:
            f.write(str(1))
        shutil.rmtree(repo_dir_copy)
        return 1



    
    
    

if __name__ == '__main__':
    pwd = os.getcwd()
    df = pd.read_csv("data/valid_repos.csv")
    merge_dir = "merges_small/"
    output_dir = "merges_small_valid/"
    

    commits = set()
    for idx,row in df.iterrows():
        repo_name = row["repository"]
        merge_list_file = merge_dir+repo_name.split("/")[1]+".csv"
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(merge_list_file,names=["merge","left","right","base"])

        for idx2, row2 in merges.iterrows():
            if len(row2["left"]) == 40 and len(row2["right"]) == 40:
                commits.add((repo_name,row2["left"]))
                commits.add((repo_name,row2["right"]))
    
    commits = list(commits)

    pool = multiprocessing.Pool(os.cpu_count())
    pool.map(pass_test,[(repo_name,commit,".workdir/","cache/commit_test_result/") for repo_name, commit in commits])

    for idx,row in df.iterrows():
        repo_name = row["repository"]
        merge_list_file = merge_dir+repo_name.split("/")[1]+".csv"
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(merge_list_file,names=["merge","left","right","base"])
        merges["parent test"] = [1 for i in merges.iterrows()]

        for idx2, row2 in merges.iterrows():
            if len(row2["left"]) == 40 and len(row2["right"]) == 40:
                test1 = pass_test((repo_name,row2["left"],".workdir/","cache/commit_test_result/"))
                test2 = pass_test((repo_name,row2["right"],".workdir/","cache/commit_test_result/"))
                if test1 == 0 and test2 == 0:
                    merges.loc[idx2, "parent test"] = 0
        outout_file = output_dir+repo_name.split("/")[1]+".csv"
        merges.to_csv(outout_file)

