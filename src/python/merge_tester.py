import pandas as pd
import git
import subprocess
import shutil
import os
import time
import multiprocessing

def test_merge(args):
    repo_name,left,right,base,working_dir,cache = args
    cache_file = cache+repo_name.split("/")[1]+"_"+left+"_"+right+"_"+base

    if os.path.isfile(cache_file):
        with open(cache_file) as f:
            git_merge,git_runtime,spork_merge,spork_runtime,intelli_merge,intelli_runtime = [int(x) for x in next(f).split()]
            return git_merge,git_runtime,spork_merge,spork_runtime,intelli_merge,intelli_runtime
    
    process = multiprocessing.current_process()
    pid = str(process.pid)

    repo_dir = "repos/"+repo_name
    pwd = os.getcwd()
    repo_dir_copy = pwd+working_dir+pid
    

    # if os.path.isdir(repo_dir_copy):
    #     shutil.rmtree(repo_dir_copy)
    # shutil.copytree(repo_dir, repo_dir_copy)
    # repo = git.Git(repo_dir_copy)
    # repo.fetch()
    try:
        shutil.copytree(repo_dir, repo_dir_copy+"/left")
        shutil.copytree(repo_dir, repo_dir_copy+"/right")
        shutil.copytree(repo_dir, repo_dir_copy+"/base")
        print(repo_dir,left)
        repo_git = git.Git(repo_dir_copy+"/left")
        repo_git.checkout(left)
        repo_git = git.Git(repo_dir_copy+"/right")
        repo_git.checkout(right)
        repo_git = git.Git(repo_dir_copy+"/base")
        repo_git.checkout(base)
        try:
            start = time.time()
            git_merge = int(subprocess.run([pwd+"/src/scripts/merge_tools/gitmerge.sh",repo_dir_copy,repo_dir_copy+"/git"]).returncode != 0)
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
        try:
            start = time.time()
            spork_merge = subprocess.run([pwd+"/spork.sh",repo_dir_copy,repo_dir_copy+"/spork"]).returncode
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
        print("TEST")
        try:
            start = time.time()
            intelli_merge = subprocess.run([pwd+"/intellimerge.sh",
                                "merge_repo/intellimerge",
                                "AOFKMAFNASFKJNRFQJXNFHJ1",
                                "AOFKMAFNASFKJNRFQJXNFHJ2",
                                repo_dir_copy+"/intellimerge"]).returncode
            intelli_runtime = time.time()-start
        except Exception:
            intelli_merge = 6
            intelli_runtime = -1
        try:
            if intelli_merge == 0:
                intelli_merge = subprocess.run([pwd+"/src/scripts/tester.sh",repo_dir_copy+"/intellimerge"]).returncode+2
        except Exception:
            intelli_merge = 5

        out = str(git_merge)+" "+str(int(git_runtime))+" "\
                +str(spork_merge)+" "+str(int(spork_runtime))+" "\
                +str(intelli_merge)+" "+str(int(intelli_runtime))
        with open(cache_file,"w") as f:
            f.write(out)
        shutil.rmtree(repo_dir_copy)
        return git_merge,git_runtime,spork_merge,spork_runtime,intelli_merge,intelli_runtime
    except Exception:
        with open(cache_file,"w") as f:
            out = "-1 -1 -1 -1 -1 -1"
            f.write(out)
        shutil.rmtree(repo_dir_copy)
        return -1,-1,-1,-1,-1,-1


if __name__ == '__main__':
    pwd = os.getcwd()
    df = pd.read_csv("data/valid_repos.csv")
    merge_dir = "merges_small_valid/"

    result = pd.DataFrame(columns = ["project name",
                                        "merge",
                                        "left",
                                        "right",
                                        "base",
                                        "parent test",
                                        "git merge",
                                        "intellimerge",
                                        "spork",
                                        "runtime git",
                                        "runtime intellimerge",
                                        "runtime spork"])

    args = []
    for idx,row in df.iterrows():
        repo_name = row["repository"]

        merge_list_file = merge_dir+repo_name.split("/")[1]+".csv"
        if not os.path.isfile(merge_list_file):
            continue
        
        repo_dir = "repos/"+repo_name
        if not os.path.isdir(repo_dir):
            git_url = "https://github.com/"+repo_name+".git"
            repo = git.Repo.clone_from(git_url, repo_dir)
            repo.remote().fetch()
        else:
            repo = git.Git(repo_dir)
        
        #repo.remote().fetch()
        
        merges = pd.read_csv(merge_list_file)

        for idx2, row2 in merges.iterrows():
            args.append((repo_name,row2["left"],row2["right"],row2["base"],"/.workdir/","cache/merge_test_results/"))

    pool = multiprocessing.Pool(os.cpu_count())
    pool.map(test_merge,args)

    for idx,row in df.iterrows():
        repo_name = row["repository"]

        merge_list_file = merge_dir+repo_name.split("/")[1]+".csv"
        if not os.path.isfile(merge_list_file):
            continue
        
        merges = pd.read_csv(merge_list_file)

        for idx2, row2 in merges.iterrows():
            git_merge,git_runtime,spork_merge,spork_runtime,intelli_merge,intelli_runtime = test_merge((repo_name,row2["left"],row2["right"],row2["base"],"/.workdir/","cache/merge_test_results/"))
            result = pd.concat([result,pd.DataFrame({"project name":repo_name,
                            "left":row2["left"],
                            "right":row2["right"],
                            "merge":row2["merge"],
                            "base":row2["base"],
                            "parent test":row2["parent test"],
                            "git merge":git_merge,
                            "spork merge":spork_merge,
                            "intellimerge":intelli_merge,
                            "git runtime":git_runtime,
                            "intellimerge runtime":intelli_runtime,
                            "spork runtime":spork_runtime},
                            index=[0])])
            result.to_csv("data/result.csv")