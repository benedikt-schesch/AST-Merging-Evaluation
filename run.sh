#!/usr/bin/env bash

# usage: ./run.sh <repo_list> <output_folder> <n_merges> [<machine_id> <num_machine>]
# <repo_list> list of repositories in csv formart with a column 
#     repository that has format owner/reponame for each repository.
# <output_folder> folder that contains all outputs.
# <n_merges> number of merges to sample for each repository.
# <machine_id> optional argument to specify the id of the current machine.
# <num_machine> optional argument to specify the total number of machines used.
# Runs the stack.
# The output appears in <output_folder> .


set -e
set -o nounset

REPOS_CSV="$1"
OUT_DIR="$2"
N_MERGES=$3
machine_id="${4:-0}"
num_machines="${5:-1}"

mvn -v | head -n 1 | cut -c 14-18 | grep -q 3.9.2 || { echo "Maven 3.9.2 is required"; exit 1; }
if [ -z "${JAVA8_HOME:+isset}" ] ; then echo "JAVA8_HOME is not set"; exit 1; fi
if [ -z "${JAVA11_HOME:+isset}" ] ; then echo "JAVA11_HOME is not set"; exit 1; fi
if [ -z "${JAVA17_HOME:+isset}" ] ; then echo "JAVA17_HOME is not set"; exit 1; fi

echo "Machine ID: $machine_id"
echo "Number of machines: $num_machines"
echo "Output directory: $OUT_DIR"

length=${#REPOS_CSV}
REPOS_CSV_WITH_HASHES="${REPOS_CSV::length-4}_with_hashes.csv"

./gradlew assemble -g ../.gradle/

mkdir -p "$OUT_DIR"

python3 src/python/write_head_hashes.py --repos_csv "$REPOS_CSV" --output_path "$REPOS_CSV_WITH_HASHES"

python3 src/python/split_repos.py --repos_csv "$REPOS_CSV_WITH_HASHES" --machine_id "$machine_id" --num_machines "$num_machines" --output_file "$OUT_DIR/local_repos.csv"

python3 src/python/validate_repos.py --repos_csv_with_hashes "$OUT_DIR/local_repos.csv" --output_path "$OUT_DIR/valid_repos.csv"

java -cp build/libs/astmergeevaluation-all.jar astmergeevaluation.FindMergeCommits "$OUT_DIR/valid_repos.csv" "$OUT_DIR/merges"

python3 src/python/parent_merges_test.py --valid_repos_csv "$OUT_DIR/valid_repos.csv" --merges_path "$OUT_DIR/merges/" --output_dir "$OUT_DIR/merges_valid/" --n_merges "$N_MERGES"

python3 src/python/merge_tester.py --valid_repos_csv "$OUT_DIR/valid_repos.csv" --merges_path "$OUT_DIR/merges_valid/" --output_file "$OUT_DIR/result.csv"

python3 src/python/latex_output.py --input_csv "$OUT_DIR/result.csv" --output_path "$OUT_DIR/plots"
