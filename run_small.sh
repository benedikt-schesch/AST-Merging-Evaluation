#!/bin/bash

# usage: ./run_small.sh
# Runs the stack on two small repos.
# The output appears in small/ .

machine_id="${1:-0}"
num_machines="${2:-1}"

echo "Machine ID: $machine_id"
echo "Number of machines: $num_machines"

set -e
set -o nounset

java -version

JAVA_VER=$(java -version 2>&1 | head -1 | cut -d'"' -f2 | sed '/^1\./s///' | cut -d'.' -f1)

if [ "$JAVA_VER" != "8" ]; then
  echo "Wrong Java version $JAVA_VER. Please use Java 8."
  exit 1
fi

python3 src/python/get_repos.py

python3 src/python/split_repos.py --repos_path data/repos_small.csv --machine_id "$machine_id" --num_machines "$num_machines" --output_file small/local_repos_small.csv

python3 src/python/validate_repos.py --repos_path small/local_repos_small.csv --output_path small/valid_repos.csv

./src/scripts/find_merge_commits.sh small/valid_repos.csv small/merges_small

python3 src/python/test_parent_merges.py --repos_path small/valid_repos.csv --merges_path small/merges_small/ --output_dir small/merges_small_valid/ --n_merges 2

python3 src/python/merge_tester.py --repos_path small/valid_repos.csv --merges_path small/merges_small_valid/ --output_file small/result.csv

python3 src/python/latex_output.py --result_path small/result.csv --output_path small/plots
