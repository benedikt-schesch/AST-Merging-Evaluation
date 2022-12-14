import pandas as pd
import git
import subprocess
import shutil
import os
import multiprocessing
from merge_tester import get_repo
from pebble import ProcessPool
import argparse
import platform
from repo_checker import test_repo

CACHE = "cache/commit_test_result/"
WORKDIR = ".workdir/"
TIMEOUT_SECONDS = 10*60

def pass_test(args):
    repo_name,commit = args
    cache_file = CACHE+repo_name.split("/")[1]+"_"+commit

    if os.path.isfile(cache_file):
        try:
            with open(cache_file) as f:
                return int(next(f))
        except Exception:
            return 1

    # Flag in case process timeouts
    with open(cache_file,"w") as f:
        f.write(str(-1))
    
    if platform.system() == "Linux": #Linux
        command_timeout = "timeout"
    else: #MacOS
        command_timeout = "gtimeout"

    process = multiprocessing.current_process()
    pid = str(process.pid)

    repo_dir = "repos/"+repo_name
    repo_dir_copy = WORKDIR+pid
    
    repo = get_repo(repo_name)

    if os.path.isdir(repo_dir_copy):
        shutil.rmtree(repo_dir_copy)
    shutil.copytree(repo_dir, repo_dir_copy)
    repo = git.Git(repo_dir_copy)
    repo.fetch()
    repo.checkout(commit)

    try:
        test = test_repo(repo_dir_copy,TIMEOUT_SECONDS)
    except Exception:
        test = 2
    
    with open(cache_file,"w") as f:
        f.write(str(test))
    shutil.rmtree(repo_dir_copy)

    return test
    

if __name__ == '__main__':
    pwd = os.getcwd()
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_path",type=str)
    parser.add_argument("--merges_path",type=str)
    parser.add_argument("--output_dir",type=str)
    args = parser.parse_args()
    df = pd.read_csv(args.repos_path)
    if os.path.isdir(args.output_dir):
        shutil.rmtree(args.output_dir)
    os.mkdir(args.output_dir)

    commits = set()
    for idx,row in df.iterrows():
        repo_name = row["repository"]
        merge_list_file = args.merges_path+repo_name.split("/")[1]+".csv"
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(merge_list_file,names=["merge","left","right","base"])

        for idx2, row2 in merges.iterrows():
            if len(row2["left"]) == 40 and len(row2["right"]) == 40:
                commits.add((repo_name,row2["left"]))
                commits.add((repo_name,row2["right"]))
                commits.add((repo_name,row2["merge"]))
    
    commits = list(commits)

    # with ProcessPool(max_workers=os.cpu_count()-10) as pool:
    #     pool.map(pass_test,commits,timeout=TIMEOUT_SECONDS)
    print("Number of tested commits:",len(commits))
    print("Started Testing")
    pool = multiprocessing.Pool(os.cpu_count()-10)
    pool.map(pass_test,commits)
    print("Finished Testing")

    for idx,row in df.iterrows():
        repo_name = row["repository"]
        merge_list_file = args.merges_path+repo_name.split("/")[1]+".csv"
        if not os.path.isfile(merge_list_file):
            continue

        merges = pd.read_csv(merge_list_file,names=["merge","left","right","base"])
        merges["parent test"] = [1 for i in merges.iterrows()]
        merges["merge test"] = [1 for i in merges.iterrows()]

        for idx2, row2 in merges.iterrows():
            if len(row2["left"]) == 40 and len(row2["right"]) == 40:
                test1 = pass_test((repo_name,row2["left"]))
                test2 = pass_test((repo_name,row2["right"]))
                if test1 == 0 and test2 == 0:
                    merges.loc[idx2, "parent test"] = 0
                    merges.loc[idx2, "merge test"] = pass_test((repo_name,row2["merge"]))
        outout_file = args.output_dir+repo_name.split("/")[1]+".csv"
        merges.to_csv(outout_file)

