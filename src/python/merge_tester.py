import pandas as pd
import git
import subprocess
import shutil
import os
import time
import multiprocessing
import pandas as pd
import argparse
import platform

SCRATCH_DIR = "scratch/" 
STORE_SCRATCH = False
WORKDIR = ".workdir/"
CACHE = "cache/merge_test_results/"
DELETE_WORKDIR = True
TIMEOUT_MERGE = 15*60 # 15 Minutes
TIMEOUT_TESTING = 30*60 # 30 Minutes


def get_repo(repo_name):
    repo_dir = "repos/"+repo_name
    if not os.path.isdir(repo_dir):
        git_url = "https://github.com/"+repo_name+".git"
        repo = git.Repo.clone_from(git_url, repo_dir)
        repo.remote().fetch()
    else:
        repo = git.Git(repo_dir)
    return repo

def test_merge(merging_method,repo_name,left,right,base):
    try:
        repo_dir = "repos/"+repo_name
        process = multiprocessing.current_process()
        pid = str(process.pid)
        repo_dir_copy = WORKDIR+pid

        if platform.system() == "Linux": #Linux
            command_timeout = "timeout"
        else: #MacOS
            command_timeout = "gtimeout"


        shutil.copytree(repo_dir, repo_dir_copy+"/"+merging_method)
        repo = git.Git(repo_dir_copy+"/"+merging_method)
        repo.fetch()
        repo.checkout(left)
        repo.checkout('-b','AOFKMAFNASFKJNRFQJXNFHJ1')
        repo.checkout(right)
        repo.checkout('-b','AOFKMAFNASFKJNRFQJXNFHJ2')
        try:
            start = time.time()
            merge = subprocess.run([command_timeout,
                                        str(TIMEOUT_MERGE)+"s",
                                        "src/scripts/merge_tools/"+merging_method+".sh",
                                        repo_dir_copy+"/"+merging_method,
                                        "AOFKMAFNASFKJNRFQJXNFHJ1",
                                        "AOFKMAFNASFKJNRFQJXNFHJ2"]).returncode
            runtime = time.time()-start
        except Exception:
            merge = 6
            runtime = -1
        try:
            if merge == 0:
                merge = subprocess.run([command_timeout,
                                        str(TIMEOUT_TESTING)+"s",
                                        "src/scripts/tester.sh",
                                        repo_dir_copy+"/"+merging_method]).returncode+2
        except Exception:
            merge = 5
    except Exception:
        merge = -1
        runtime = -1
    if DELETE_WORKDIR:
        shutil.rmtree(repo_dir_copy)
    if STORE_SCRATCH:
        if os.path.isdir(repo_dir_copy+"/"+merging_method):
            dst_name = SCRATCH_DIR+repo_name+"_"+left+"_"+right+"_"+base+"_"+merging_method
            shutil.copytree(repo_dir_copy+"/"+merging_method,dst_name)
    return merge, runtime


def test_merges(args):
    repo_name,left,right,base,merge,merge_test = args
    if type(right) != str or type(left) != str or type(base) != str or type(base) != str:
        return pd.DataFrame()
    cache_file = CACHE+repo_name.split("/")[1]+"_"+left+"_"+right+"_"+base+".csv"

    if os.path.isfile(cache_file):
        return pd.read_csv(cache_file,index_col=0)
    
    out = pd.DataFrame([[repo_name,
                                left,
                                right,
                                base,
                                merge,
                                -2,
                                -2,
                                -2,
                                -2,
                                -2,
                                -2,
                                merge_test]])
    out.to_csv(cache_file)
    
    #Git Merge
    git_merge, git_runtime = test_merge("gitmerge",repo_name,left,right,base)

    #Spork Merge
    spork_merge, spork_runtime = test_merge("spork",repo_name,left,right,base)

    #IntelliMerge
    intelli_merge, intelli_runtime = test_merge("intellimerge",repo_name,left,right,base)

    out = pd.DataFrame([[repo_name,
                            left,
                            right,
                            base,
                            merge,
                            git_merge,
                            spork_merge,
                            intelli_merge,
                            git_runtime,
                            spork_runtime,
                            intelli_runtime,
                            merge_test]])
    out.to_csv(cache_file)
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
                                        "merge",
                                        "git merge",
                                        "spork",
                                        "intellimerge",
                                        "runtime git",
                                        "runtime spork",
                                        "runtime intellimerge",
                                        "merge test"])

    args_merges = []
    for idx,row in df.iterrows():
        repo_name = row["repository"]

        merge_list_file = merge_dir+repo_name.split("/")[1]+".csv"
        if not os.path.isfile(merge_list_file):
            continue
        
        merges = pd.read_csv(merge_list_file)

        for idx2, row2 in merges.iterrows():
            args_merges.append((repo_name,
                                row2["left"],
                                row2["right"],
                                row2["base"],
                                row2["merge"],
                                row2["merge test"]))


    pool = multiprocessing.Pool(os.cpu_count()-10)
    pool.map(test_merges,args_merges)

    for idx,row in df.iterrows():
        repo_name = row["repository"]

        merge_list_file = merge_dir+repo_name.split("/")[1]+".csv"
        if not os.path.isfile(merge_list_file):
            continue
        
        merges = pd.read_csv(merge_list_file)

        for idx2, row2 in merges.iterrows():
            if type(row2["left"]) != str or type(row2["right"]) != str or type(row2["base"]) != str:
                continue
            res = test_merges((repo_name,
                                row2["left"],
                                row2["right"],
                                row2["base"],
                                row2["merge"],
                                row2["merge test"]))
            res.columns = result.columns
            result = pd.concat([result,res],axis=0,ignore_index=True)
            result.to_csv(args.output_file)