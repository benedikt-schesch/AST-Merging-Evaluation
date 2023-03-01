#!/bin/bash

# usage: ./run_cf.sh
# Runs the stack on the cf repos.
# The output appears in cf/ .

machine_id="${1:-0}"
num_machines="${2:-1}"

echo "Machine ID: $machine_id"
echo "Number of machines: $num_machines"

set -e 
set -o nounset

JAVA_VER=$(java -version 2>&1 | head -1 | cut -d'"' -f2 | sed '/^1\./s///' | cut -d'.' -f1)

if [ "$JAVA_VER" != "8" ]; then
  echo "Wrong Java version $JAVA_VER. Please use Java 8."
  exit 1
fi

mkdir -p cf

python3 src/python/validate_repos.py --repos_path data/repos_cf.csv --output_path cf/valid_repos.csv

python3 src/python/split_repos.py --repos_path data/valid_repos.csv --machine_id "$machine_id" --num_machines "$num_machines" --output_file cf/local_repos_cf.csv

./src/scripts/find_merge_commits.sh cf/local_repos_cf.csv cf/merges_cf

python3 src/python/parent_merges_test.py --repos_path cf/local_repos_cf.csv --merges_path cf/merges_cf/ --output_dir cf/merges_cf_valid/ --n_merges 2

python3 src/python/merge_tester.py --repos_path cf/local_repos_cf.csv --merges_path cf/merges_cf_valid/ --output_file cf/result.csv

python3 src/python/latex_output.py --result_path small/result.csv --output_path small/plots
