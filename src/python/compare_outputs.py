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
STORE_SCRATCH = True

def compare_outputs(args):
    idx, row = args
    repo_name,left,right,base = row["project name"], row["left"], row["right"], row["base"]
    merging_methods = ["git merge","spork","intellimerge"]
    for idx, method1 in enumerate(merging_methods):
        for method2 in merging_methods[idx+1:]:
            dst_name1 = SCRATCH_DIR+repo_name+"_"+left+"_"+right+"_"+base+"_"+method1
            dst_name2 = SCRATCH_DIR+repo_name+"_"+left+"_"+right+"_"+base+"_"+method2
            result = 0#subprocess.run([dst_name1,dst_name2]).returncode
            row[method1+" "+method2+" output"] = result
    return row




if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--result_path",type=str)
    parser.add_argument("--output_path",type=str)
    args = parser.parse_args()
    df = pd.read_csv(args.result_path,index_col=0)

    pool = multiprocessing.Pool(os.cpu_count()-5)
    result = pool.map(compare_outputs,df.iterrows())
    pool.close()
    result = pd.DataFrame(result)
    result.to_csv(args.output_path)