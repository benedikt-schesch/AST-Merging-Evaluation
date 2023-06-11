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

JAVA_VER=$(java -version 2>&1 | head -1 | cut -d'"' -f2 | sed '/^1\./s///' | cut -d'.' -f1)

# This project has been eecuted with Java 8 and might yield different results with other versions.
# Java 8 returned the largest amount of valid repositories.
if [ "$JAVA_VER" != "8" ]; then
  echo "Wrong Java version $JAVA_VER. Please use Java 8."
  exit 1
fi

echo "Machine ID: $machine_id"
echo "Number of machines: $num_machines"
echo "Output directory: $OUT_DIR"

length=${#REPOS_CSV}
REPOS_CSV_WITH_HASHES="${REPOS_CSV::length-4}_with_hashes.csv"
SCRIPT_PATH=$(dirname "$0"); SCRIPT_PATH=$(eval "cd \"$SCRIPT_PATH\" && pwd")
ROOT_PATH=$(realpath "${SCRIPT_PATH}/../../../")
intellimergefullpath="${ROOT_PATH}/jars/IntelliMerge-1.0.9-all.jar"
sporkfullpath="${ROOT_PATH}/jars/spork.jar"

# If file ${sporkfullpath} does not exist download spork
if [ ! -f "${sporkfullpath}" ]; then
    make download-spork
fi

# If file ${intellimergefullpath} does not exist download intellimerge
if [ ! -f "${intellimergefullpath}" ]; then
    make download-intellimerge
fi

./gradlew assemble

mkdir -p "$OUT_DIR"

python3 src/python/get_repos.py

python3 src/python/write_head_hashes.py --repos_csv "$REPOS_CSV" --output_path "$REPOS_CSV_WITH_HASHES"

python3 src/python/split_repos.py --repos_csv "$REPOS_CSV_WITH_HASHES" --machine_id "$machine_id" --num_machines "$num_machines" --output_file "$OUT_DIR/local_repos.csv"

python3 src/python/validate_repos.py --repos_csv "$OUT_DIR/local_repos.csv" --output_path "$OUT_DIR/valid_repos.csv"

java -cp build/libs/astmergeevaluation-all.jar astmergeevaluation.FindMergeCommits "$OUT_DIR/valid_repos.csv" "$OUT_DIR/merges"

python3 src/python/parent_merges_test.py --repos_csv "$OUT_DIR/valid_repos.csv" --merges_path "$OUT_DIR/merges/" --output_dir "$OUT_DIR/merges_valid/" --n_merges "$N_MERGES"

python3 src/python/merge_tester.py --repos_csv "$OUT_DIR/valid_repos.csv" --merges_path "$OUT_DIR/merges_valid/" --output_file "$OUT_DIR/result.csv"

python3 src/python/latex_output.py --input_csv "$OUT_DIR/result.csv" --output_path "$OUT_DIR/plots"
