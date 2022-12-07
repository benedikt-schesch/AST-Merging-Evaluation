import pandas as pd
from git import Repo
import subprocess
import shutil
import os
import multiprocessing
from merge_tester import get_repo
import argparse
from tqdm import tqdm
import platform

CACHE = "cache/repos_result/"
WORKDIR = ".workdir/"
TIMEOUT_MERGE = 20*60

def check_repo(arg):
    idx,row = arg
    repo_name = row["repository"]

    if platform.system() == "Linux": #Linux
        command_timeout = "timeout"
    else: #MacOS
        command_timeout = "gtimeout"

    repo_dir = "repos/"+repo_name
    target_file = CACHE+repo_name.replace("/","_")+".csv"

    if os.path.isfile(target_file):
        df = pd.read_csv(target_file)
        return df.iloc[0]["test"]

    df = pd.DataFrame({"test":[1]})
    df.to_csv(target_file)
    pid = str(multiprocessing.current_process().pid)
    repo_dir_copy = WORKDIR+pid
    try:
        repo = get_repo(repo_name)
        shutil.copytree(repo_dir, repo_dir_copy)

        pwd = os.getcwd()
        rc = subprocess.run([command_timeout,
                                str(TIMEOUT_MERGE)+"s",
                                pwd+"/src/scripts/tester.sh",
                                repo_dir_copy]).returncode

        df = pd.DataFrame({"test":[rc]})
        df.to_csv(target_file)
    except Exception:
        pass
    shutil.rmtree(repo_dir_copy)
    return df.iloc[0]["test"]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos_path",type=str)
    parser.add_argument("--output_path",type=str)
    args = parser.parse_args()
    df = pd.read_csv(args.repos_path)

    for idx,row in tqdm(df.iterrows(),total=len(df)):
        repo_name = row["repository"]
        repo = get_repo(repo_name)

    print("Start processing")
    pool = multiprocessing.Pool(processes=os.cpu_count()-10)
    pool.map(check_repo, df.iterrows())
    print("End processing")
    
    out = []
    for idx,row in df.iterrows():
        repo_name = row["repository"]
        repo = check_repo((idx,row))
        if repo == 0:
            out.append(row)
    out = pd.DataFrame(out)
    out.to_csv(args.output_path)