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

    result = pd.DataFrame(columns = ["project name",
                                        "merge",
                                        "left",
                                        "right",
                                        "base",
                                        "parent test",
                                        "git merge",
                                        "intellimerge",
                                        "spork"])

    for idx,row in df.iterrows():
        repo_name = row["repository"]
        print(repo_name)
        merge_list_file = "merges/"+repo_name.split("/")[1]+".csv"
        if not os.path.isfile(merge_list_file):
            continue
        
        merges = pd.read_csv(merge_list_file,names=["merge","left","right","base","parent test"])

        if len(merges) > 20:
            continue

        repo_dir = "repos/"+repo_name


        if not os.path.isdir(repo_dir):
            git_url = "https://github.com/"+repo_name+".git"
            repo = git.Repo.clone_from(git_url, repo_dir)
        else:
            repo = git.Git(repo_dir)
        repo.fetch()

        for idx2, row2 in merges.iterrows():
            if row2["parent test"] == 1:
                continue
            #Git Merge
            a = time.time()
            for i in ["left","right","base"]:
                repo.checkout(row2[i])
                if os.path.isdir("merge_repo/"+i):
                    shutil.rmtree("merge_repo/"+i)
                shutil.copytree(repo_dir, "merge_repo/"+i)
            if os.path.isdir("merge_repo/git"):
                shutil.rmtree("merge_repo/git")
            git_merge = int(subprocess.run([pwd+"/gitmerge.sh","merge_repo/","merge_repo/git"]).returncode != 0)
            print("Git:",time.time()-a)
            if git_merge == 0:
                git_merge = subprocess.run([pwd+"/tester.sh","merge_repo/git"]).returncode+1

            #Spork Merge
            # a = time.time()
            # repo.checkout(row2["base"])
            # if os.path.isdir("merge_repo/base"):
            #     shutil.rmtree("merge_repo/base")
            # shutil.copytree(repo_dir, "merge_repo/base")
            
            # rc = subprocess.run([pwd+"/spork.sh","merge_repo/","merge_repo/spork"]).returncode
            # if rc == 0:
            #     rc = subprocess.run([pwd+"/tester.sh","merge_repo/spork"]).returncode
            # print("Spork:",time.time()-a)


            #IntelliMerge
            a = time.time()
            if os.path.isdir("merge_repo/intellimerge"):
                shutil.rmtree("merge_repo/intellimerge")
            shutil.copytree(repo_dir, "merge_repo/intellimerge")
            repo_intelli = git.Git("merge_repo/intellimerge")
            repo_intelli.checkout(row2["left"])
            repo_intelli.checkout('-b','AOFKMAFNASFKJNRFQJXNFHJ1')
            repo_intelli.checkout(row2["right"])
            repo_intelli.checkout('-b','AOFKMAFNASFKJNRFQJXNFHJ2')
            print("IntelliMerge:",time.time()-a)


            intelli_merge = subprocess.run([pwd+"/intellimerge.sh",
                                    "merge_repo/intellimerge",
                                    "AOFKMAFNASFKJNRFQJXNFHJ1",
                                    "AOFKMAFNASFKJNRFQJXNFHJ2",
                                    "merge_repo/intellimerge"]).returncode
            if intelli_merge == 0:
                intelli_merge = subprocess.run([pwd+"/tester.sh","merge_repo/base"]).returncode+1

            result = result.append({"project name":repo_name,
                            "left":row2["left"],
                            "right":row2["right"],
                            "merge":row2["merge"],
                            "base":row2["base"],
                            "parent test":row2["parent test"],
                            "git merge":git_merge,
                            "intellimerge":intelli_merge,
                            "spork":0}, ignore_index=True)
            result.to_csv("result.csv")
        # if idx == 1:
        #     break