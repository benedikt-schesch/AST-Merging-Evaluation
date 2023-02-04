#!/bin/bash

# usage: ./run_small.sh <num_cpus>
# Runs the stack on small repos

set -e 
set -o nounset

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 NUM_CPUS" >&2
  exit 1
fi

python3 src/python/repo_checker.py --repos_path data/repos_small.csv --output_path small/valid_repos.csv  --num_cpu "$1"

sh src/scripts/find_merge_commits.sh small/valid_repos.csv small/merges_small

python3 src/python/test_parent_merges.py --repos_path small/valid_repos.csv --merges_path small/merges_small/ --output_dir small/merges_small_valid/ --num_cpu "$1" --n_merges 2

python3 src/python/merge_tester.py --repos_path small/valid_repos.csv --merges_path small/merges_small_valid/ --output_file small/result.csv  --num_cpu "$1"
