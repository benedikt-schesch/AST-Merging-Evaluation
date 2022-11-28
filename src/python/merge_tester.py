import pandas as pd
import git
import subprocess
import shutil
import os
import time
import multiprocessing
import pandas as pd
import argparse
from pebble import ProcessPool

SCRATCH_DIR = "scratch/" 
STORE_SCRATCH = False
WORKDIR = ".workdir/"
CACHE = "cache/merge_test_results/"
DELETE_WORKDIR = True
TIMEOUT_SECONDS = 60*60


def get_repo(repo_name):
    repo_dir = "repos/"+repo_name
    if not os.path.isdir(repo_dir):
        git_url = "https://github.com/"+repo_name+".git"
        repo = git.Repo.clone_from(git_url, repo_dir)
        repo.remote().fetch()
    else:
        repo = git.Git(repo_dir)
    return repo


def test_merge(args):
    repo_name,left,right,base = args
    cache_file = CACHE+repo_name.split("/")[1]+"_"+left+"_"+right+"_"+base+".csv"

    if os.path.isfile(cache_file):
        return pd.read_csv(cache_file,index_col=0)
    
    out = pd.DataFrame([[repo_name,
                                left,
                                right,
                                base,
                                -2,
                                -2,
                                -2,
                                -2,
                                -2,
                                -2]])
    out.to_csv(cache_file)
    
    process = multiprocessing.current_process()
    pid = str(process.pid)

    repo_dir = "repos/"+repo_name
    pwd = os.getcwd()
    repo_dir_copy = WORKDIR+pid
    
    try:
        #Git Merge
        shutil.copytree(repo_dir, repo_dir_copy+"/git")
        repo_git = git.Git(repo_dir_copy+"/git")
        repo_git.fetch()
        repo_git.checkout(left)
        repo_git.checkout('-b','AOFKMAFNASFKJNRFQJXNFHJ1')
        repo_git.checkout(right)
        repo_git.checkout('-b','AOFKMAFNASFKJNRFQJXNFHJ2')
        try:
            start = time.time()
            git_merge = int(subprocess.run([pwd+"/src/scripts/merge_tools/gitmerge.sh",repo_dir_copy+"/git","AOFKMAFNASFKJNRFQJXNFHJ1","AOFKMAFNASFKJNRFQJXNFHJ2"]).returncode != 0)
            git_runtime = time.time()-start
        except Exception:
            git_merge = 6
            git_runtime = -1
        try:
            if git_merge == 0:
                git_merge = subprocess.run([pwd+"/src/scripts/tester.sh",repo_dir_copy+"/git"]).returncode+2
        except Exception:
            git_merge = 5

        #Spork Merge
        shutil.copytree(repo_dir, repo_dir_copy+"/spork")
        repo_git = git.Git(repo_dir_copy+"/spork")
        repo_git.fetch()
        repo_git.checkout(left)
        repo_git.checkout('-b','AOFKMAFNASFKJNRFQJXNFHJ1')
        repo_git.checkout(right)
        repo_git.checkout('-b','AOFKMAFNASFKJNRFQJXNFHJ2')
        try:
            start = time.time()
            spork_merge = subprocess.run([pwd+"/src/scripts/merge_tools/spork.sh",
                                repo_dir_copy+"/spork",
                                "AOFKMAFNASFKJNRFQJXNFHJ1",
                                "AOFKMAFNASFKJNRFQJXNFHJ2"]).returncode
            spork_runtime = time.time()-start
        except Exception:
            spork_merge = 6
            spork_runtime = -1
        try:
            if spork_merge == 0:
                spork_merge = subprocess.run([pwd+"/src/scripts/tester.sh",repo_dir_copy+"/spork"]).returncode+2
        except Exception:
            spork_merge = 5

        #IntelliMerge
        shutil.copytree(repo_dir, repo_dir_copy+"/intellimerge")
        repo_intelli = git.Git(repo_dir_copy+"/intellimerge")
        repo_intelli.fetch()
        repo_intelli.checkout(left)
        repo_intelli.checkout('-b','AOFKMAFNASFKJNRFQJXNFHJ1')
        repo_intelli.checkout(right)
        repo_intelli.checkout('-b','AOFKMAFNASFKJNRFQJXNFHJ2')
        try:
            start = time.time()
            intelli_merge = subprocess.run([pwd+"/src/scripts/merge_tools/intellimerge.sh",
                                repo_dir_copy+"/intellimerge",
                                "AOFKMAFNASFKJNRFQJXNFHJ1",
                                "AOFKMAFNASFKJNRFQJXNFHJ2"]).returncode
            intelli_runtime = time.time()-start
        except Exception:
            intelli_merge = 6
            intelli_runtime = -1
        try:
            if intelli_merge == 0:
                intelli_merge = subprocess.run([pwd+"/src/scripts/tester.sh",repo_dir_copy+"/intellimerge"]).returncode+2
        except Exception:
            intelli_merge = 5

        if STORE_SCRATCH:
            for i in ["git","spork","intellimerge"]:
                if os.path.isdir(repo_dir_copy+"/"+i):
                    dst_name = SCRATCH_DIR+repo_name+"_"+left+"_"+right+"_"+base+"_"+i
                    shutil.copytree(repo_dir_copy+"/"+i,dst_name)

        out = pd.DataFrame([[repo_name,
                                left,
                                right,
                                base,
                                git_merge,
                                spork_merge,
                                intelli_merge,
                                git_runtime,
                                spork_runtime,
                                intelli_runtime]])
        out.to_csv(cache_file)
        if DELETE_WORKDIR:
            shutil.rmtree(repo_dir_copy)
        return out
    except Exception:
        out = pd.DataFrame([[repo_name,
                                left,
                                right,
                                base,
                                -1,
                                -1,
                                -1,
                                -1,
                                -1,
                                -1]])
        out.to_csv(cache_file)
        if DELETE_WORKDIR:
            shutil.rmtree(repo_dir_copy)
        return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_path",type=str)
    parser.add_argument("--merges_path",type=str)
    parser.add_argument("--output_file",type=str)
    args = parser.parse_args()
    df = pd.read_csv(args.repos_path)
    merge_dir = args.merges_path

    result = pd.DataFrame(columns = ["project name",
                                        "left",
                                        "right",
                                        "base",
                                        "git merge",
                                        "spork",
                                        "intellimerge",
                                        "runtime git",
                                        "runtime spork",
                                        "runtime intellimerge"])

    args_merges = []
    for idx,row in df.iterrows():
        repo_name = row["repository"]

        merge_list_file = merge_dir+repo_name.split("/")[1]+".csv"
        if not os.path.isfile(merge_list_file):
            continue
        
        merges = pd.read_csv(merge_list_file)

        for idx2, row2 in merges.iterrows():
            args_merges.append((repo_name,row2["left"],row2["right"],row2["base"]))

    
    with ProcessPool(os.cpu_count()) as pool:
        pool.map(test_merge,args_merges,timeout=TIMEOUT_SECONDS)

    # pool = multiprocessing.Pool(os.cpu_count())
    # pool.map(test_merge,args_merges)

    for idx,row in df.iterrows():
        repo_name = row["repository"]

        merge_list_file = merge_dir+repo_name.split("/")[1]+".csv"
        if not os.path.isfile(merge_list_file):
            continue
        
        merges = pd.read_csv(merge_list_file)

        for idx2, row2 in merges.iterrows():
            res = test_merge((repo_name,row2["left"],row2["right"],row2["base"]))
            res.columns = result.columns
            result = pd.concat([result,res],axis=0,ignore_index=True)
            result.to_csv(args.output_file)