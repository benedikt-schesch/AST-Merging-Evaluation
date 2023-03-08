#!/bin/bash

# usage: ./run.sh <repo_list> <output_folder> <n_merges> <machine_id> <num_machine>
# <repo_list> list of repositories.
# <output_folder> folder that contains all outputs.
# <n_merges> number of merges to sample for each repository.
# <machine_id> optional argument to specify the id of the current machine.
# <num_machine> optional argument to specify the total number of machines used.
# Runs the stack.
# The output appears in <output_folder> .


set -e
set -o nounset

REPOS_PATH="$1"
OUT_DIR="$2"
N_MERGES=$3
machine_id="${4:-0}"
num_machines="${5:-1}"

JAVA_VER=$(java -version 2>&1 | head -1 | cut -d'"' -f2 | sed '/^1\./s///' | cut -d'.' -f1)

if [ "$JAVA_VER" != "8" ]; then
  echo "Wrong Java version $JAVA_VER. Please use Java 8."
  exit 1
fi

echo "Machine ID: $machine_id"
echo "Number of machines: $num_machines"

length=${#REPOS_PATH}
REPOS_PATH_WITH_HASHES="${REPOS_PATH::length-4}_with_hashes.csv"

python3 src/python/get_repos.py

python3 src/python/store_main_hashes.py --repos_path "$REPOS_PATH" --output_path "$REPOS_PATH_WITH_HASHES"

python3 src/python/split_repos.py --repos_path "$REPOS_PATH_WITH_HASHES" --machine_id "$machine_id" --num_machines "$num_machines" --output_file "$OUT_DIR/local_repos.csv"

python3 src/python/validate_repos.py --repos_path "$OUT_DIR/local_repos.csv" --output_path "$OUT_DIR/valid_repos.csv"

./src/scripts/find_merge_commits.sh "$OUT_DIR/valid_repos.csv" "$OUT_DIR/merges"

python3 src/python/parent_merges_test.py --repos_path "$OUT_DIR/valid_repos.csv" --merges_path "$OUT_DIR/merges/" --output_dir "$OUT_DIR/merges_valid/" --n_merges "$N_MERGES"

python3 src/python/merge_tester.py --repos_path "$OUT_DIR/valid_repos.csv" --merges_path "$OUT_DIR/merges_valid/" --output_file "$OUT_DIR/result.csv"

python3 src/python/latex_output.py --result_path "$OUT_DIR/result.csv" --output_path "$OUT_DIR/plots"
