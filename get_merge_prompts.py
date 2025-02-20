# -*- coding: utf-8 -*-
from pathlib import Path
import re
import os
import pandas as pd


df_path = Path("results/combined_sampled_10/result_adjusted.csv")
idx = "15682-1171"

df = pd.read_csv(df_path)
row = df.loc[df["idx"] == idx]

print("Do you want to run the merge replay script? (y/n)")
if input() == "y":
    script = (
        f"python3 src/python/replay_merge.py --merges_csv {df_path} --idx {idx} "
        "-skip_build --merge_tools deepseekr1_merge,o3_mini_high_merge,mergiraf"
    )
    os.system(script)

print("Deepseek result:", row["deepseekr1_merge"].values[0])
print("O3_mini_high result:", row["o3_mini_high_merge"].values[0])
print("Mergiraf result:", row["mergiraf"].values[0])

left = row["left"].values[0]
right = row["right"].values[0]
repo_slug = row["repository"].values[0]
repo_owner = repo_slug.split("/")[0]
repo_name = repo_slug.split("/")[1]

deepseek_log = (
    f"cache/sha_cache_entry/{repo_owner}/logs/{left}_{right}_deepseekr1_merge.log"
)
o3_mini_high_log = (
    f"cache/sha_cache_entry/{repo_owner}/logs/{left}_{right}_o3_mini_high_merge.log"
)


# Open the deepseek log and look for all paths of the regex form: queries_cache/*.cache print these paths
# e.g. "Cache file path: queries_cache/openai/o3-mini-high/40920303b0283aa65616c9e3cf542cf02f215777cdbe13a907e37b4b3156d0d6.cache"
# There can be text before and/or after the path, only extract and print the path itself
deepseek_paths = set()
with open(deepseek_log, "r", encoding="utf-8") as f:
    for line in f:
        match = re.search(r"(queries_cache/.*?\.cache)", line)
        if match:
            deepseek_paths.add(match.group(1))
print("Deepseek merge log:", deepseek_log)
print("Deepseek cache paths:")
for path in deepseek_paths:
    print(path)

# Same but for o3_mini_high
o3_mini_high_paths = set()
with open(o3_mini_high_log, "r", encoding="utf-8") as f:
    for line in f:
        match = re.search(r"(queries_cache/.*?\.cache)", line)
        if match:
            o3_mini_high_paths.add(match.group(1))
print("O3 Mini high merge log:", o3_mini_high_log)
print("O3_mini_high cache paths:")
for path in o3_mini_high_paths:
    print(path)


deepseek_path = Path(
    f".workdir/{repo_slug}-merge-replay-deepseekr1_merge-{left}-{right}/{repo_name}"
)
o3_mini_high_path = Path(
    f".workdir/{repo_slug}-merge-replay-o3_mini_high_merge-{left}-{right}/{repo_name}"
)
mergiraf_path = Path(
    f".workdir/{repo_slug}-merge-replay-mergiraf-{left}-{right}/{repo_name}"
)
programmer_path = Path(
    f".workdir/{repo_slug}-merge-input-programmer-{left}-{right}/{repo_name}"
)


# Diff deepseek and mergiraf but ignore all .git files
# diff -r -x ".git**" deepseek_path mergiraf_path
possiblities = [
    ("deepseek", deepseek_path),
    ("o3_mini_high", o3_mini_high_path),
    ("mergiraf", mergiraf_path),
    ("programmer", programmer_path),
]
for name, path in possiblities:
    for other_name, other_path in possiblities:
        if name != other_name:
            print(f"To diff {name} and {other_name}:")
            print(f'diff -r -x ".git**" {path} {other_path}')

test_script_deepseek = f"./src/scripts/run_repo_tests.sh {deepseek_path}"
test_script_o3_mini_high = f"./src/scripts/run_repo_tests.sh {o3_mini_high_path}"
test_script_mergiraf = f"./src/scripts/run_repo_tests.sh {mergiraf_path}"
test_script_programmer = f"./src/scripts/run_repo_tests.sh {programmer_path}"
print("To test deepseek: ", test_script_deepseek)
print("To test o3_mini_high: ", test_script_o3_mini_high)
print("To test mergiraf: ", test_script_mergiraf)
print("To test programmer: ", test_script_programmer)
