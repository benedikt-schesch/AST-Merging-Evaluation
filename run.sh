#!/bin/bash

# usage: ./run.sh
# Runs the stack.
# Takes a long time (days).
# The output appears in results/ .


set -e
set -o nounset

JAVA_VER=$(java -version 2>&1 | head -1 | cut -d'"' -f2 | sed '/^1\./s///' | cut -d'.' -f1)

if [ "$JAVA_VER" != "8" ]; then
  echo "Wrong Java version $JAVA_VER. Please use Java 8."
  exit 1
fi

python3 src/python/get_repos.py

python3 src/python/split_repos.py --repos_path data/repos.csv --machine_id 0 --num_machines 1 --output_file results/local_repos.csv

python3 src/python/validate_repos.py --repos_path results/local_repos.csv --output_path results/valid_repos.csv

sh src/scripts/find_merge_commits.sh results/valid_repos.csv results/merges

python3 src/python/test_parent_merges.py --repos_path results/valid_repos.csv --merges_path results/merges/ --output_dir results/merges_valid/ --n_merges 100

python3 src/python/merge_tester.py --repos_path results/valid_repos.csv --merges_path results/merges_valid/ --output_file results/result.csv

python3 src/python/latex_output.py --result_path results/result.csv --output_path results/plots
