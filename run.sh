#!/bin/bash

# usage: ./run.sh <num_cpus>
# Runs the stack

set -e 
set -o nounset

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 NUM_CPUS" >&2
  exit 1
fi

java -version

python3 src/python/repo_checker.py --repos_path data/repos.csv --output_path results/valid_repos.csv --num_cpu "$1"

sh src/scripts/find_merge_commits.sh results/valid_repos.csv results/merges

python3 src/python/test_parent_merges.py --repos_path results/valid_repos.csv --merges_path results/merges/ --output_dir results/merges_valid/ --num_cpu "$1" --n_merges 100

python3 src/python/merge_tester.py --repos_path results/valid_repos.csv --merges_path results/merges_valid/ --output_file results/result.csv --num_cpu "$1"
