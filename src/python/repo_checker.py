import pandas as pd
from git import Repo
import subprocess
import shutil
import os
import multiprocessing
from pebble import ProcessPool
from merge_tester import get_repo

def check_repo(arg):
    idx,row = arg
    repo_name = row["repository"]

    repo_dir = "repos/"+repo_name
    target_file = "cache/result/"+repo_name.replace("/","_")+".txt"

    if os.path.isfile(target_file):
       return

    with open(target_file,'w') as fp:
        fp.write(str(1))
    
    try:
        repo = get_repo(repo_name)

        pwd = os.getcwd()
        rc = subprocess.run([pwd+"/src/scripts/tester.sh",repo_dir])

        with open(target_file,'w') as fp:
            fp.write(str(rc.returncode))
    except Exception:
        pass


if __name__ == '__main__':
    df = pd.read_csv("data/repos_small.csv")

    with ProcessPool() as pool:
        future = pool.map(check_repo, df.iterrows(), timeout=10*60)

        iterator = future.result()
        while True:
            try:
                result = next(iterator)
            except StopIteration:
                break
            except TimeoutError as error:
                print("function took longer than %d seconds" % error.args[1])
    
    out = []
    for idx,row in df.iterrows():
        repo_name = row["repository"]
        repo_dir = "repos/"+repo_name
        target_file = "cache/result/"+repo_name.replace("/","_")+".txt"
        if os.path.isfile(target_file):
            with open(target_file) as fp:
                if int(next(fp)) == 0:
                    out.append(row)
    out = pd.DataFrame(out)
    out.to_csv("data/valid_repos.csv")