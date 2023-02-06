#!/bin/bash

# usage: ./run.sh
# Runs the stack

set -e 
set -o nounset

java --version

JAVA_VER=$(java -version 2>&1 | sed -n ';s/.* version "\(.*\)\.\(.*\)\..*".*/\1\2/p;')

if [ $JAVA_VER != "18" ]; then
  echo "Wrong Java version. Please use JAVA 8"
  exit 1
fi

python3 src/python/repo_checker.py --repos_path data/repos.csv --output_path results/valid_repos.csv

sh src/scripts/find_merge_commits.sh results/valid_repos.csv results/merges

python3 src/python/test_parent_merges.py --repos_path results/valid_repos.csv --merges_path results/merges/ --output_dir results/merges_valid/ --n_merges 100

python3 src/python/merge_tester.py --repos_path results/valid_repos.csv --merges_path results/merges_valid/ --output_file results/result.csv
