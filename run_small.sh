#!/bin/bash

# usage: ./run_small.sh
# Runs the stack on two small repos

set -e 
set -o nounset

java -version

JAVA_VER=$(java -version 2>&1 | sed -n ';s/.* version "\(.*\)\.\(.*\)\..*".*/\1\2/p;')

if [ $JAVA_VER != "18" ]; then
  echo "Wrong Java version. Please use JAVA 8"
  exit 1
fi

python3 src/python/repo_checker.py --repos_path data/repos_small.csv --output_path small/valid_repos.csv

sh src/scripts/find_merge_commits.sh small/valid_repos.csv small/merges_small

python3 src/python/test_parent_merges.py --repos_path small/valid_repos.csv --merges_path small/merges_small/ --output_dir small/merges_small_valid/ --n_merges 2

python3 src/python/merge_tester.py --repos_path small/valid_repos.csv --merges_path small/merges_small_valid/ --output_file small/result.csv
