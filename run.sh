#!/usr/bin/env bash

# usage: ./run.sh <repo_list> <output_folder> <n_merges> [-i <machine_id> -n <num_machines>] [-d]
# <repo_list> list of repositories in csv formart with a column
#     repository that has format owner/reponame for each repository.
# <output_folder> folder that contains all outputs.
# <n_merges> number of merges to sample for each repository.
# <machine_id> optional argument to specify the id of the current machine.
# <num_machine> optional argument to specify the total number of machines used.
# <diff> optional argument to specify whether to diff the merges.
# Runs the stack.
# The output appears in <output_folder>.


set -e
set -o nounset

REPOS_CSV="$1"
OUT_DIR="$2"
N_MERGES=$3
CACHE_DIR="${4}"

flags=""
while [ $# -gt 0 ]; do
  case $1 in
    -i | --machine_id)
    machine_id=$2
    shift
    ;;
    -n | --num_machines)
    num_machines=$2
    shift
    ;;
  esac
  shift
done

if ! command -v git-hires-merge &> /dev/null
then
    echo "git-hires-merge is not on the PATH"
    echo "Run: export PATH=$(pwd)/src/scripts/merge_tools/:\$PATH"
    echo "Alternatively, you can run: echo 'export PATH=$(pwd)/src/scripts/merge_tools/:\$PATH' >> ~/.bashrc"
    exit 1
fi

mvn -v | head -n 1 | cut -c 14-18 | grep -q 3.9. || { echo "Maven 3.9.* is required"; mvn -v; echo "PATH=$PATH"; exit 1; }
if [ -z "${JAVA8_HOME:+isset}" ] ; then echo "JAVA8_HOME is not set"; exit 1; fi
if [ -z "${JAVA11_HOME:+isset}" ] ; then echo "JAVA11_HOME is not set"; exit 1; fi
if [ -z "${JAVA17_HOME:+isset}" ] ; then echo "JAVA17_HOME is not set"; exit 1; fi

if [ -z "${machine_id:+isset}" ] ; then machine_id=0; fi
if [ -z "${num_machines:+isset}" ] ; then num_machines=1; fi

echo "Machine ID: $machine_id"
echo "Number of machines: $num_machines"
echo "Output directory: $OUT_DIR"
echo "Options: $flags"

length=${#REPOS_CSV}
REPOS_CSV_WITH_HASHES="${REPOS_CSV::length-4}_with_hashes.csv"

./gradlew assemble -g ../.gradle/

mkdir -p "$OUT_DIR"

# Delete all locks in cache
if [ -d "$CACHE_DIR" ]; then
    find "$CACHE_DIR" -name "*.lock" -delete
fi

python3 src/python/clean_cache_placeholders.py \
    --cache_dir "$CACHE_DIR"

python3 src/python/write_head_hashes.py \
    --repos_csv "$REPOS_CSV" \
    --output_path "$REPOS_CSV_WITH_HASHES"

python3 src/python/split_repos.py \
    --repos_csv "$REPOS_CSV_WITH_HASHES" \
    --machine_id "$machine_id" \
    --num_machines "$num_machines" \
    --output_file "$OUT_DIR/local_repos.csv"

python3 src/python/validate_repos.py \
    --repos_csv_with_hashes "$OUT_DIR/local_repos.csv" \
    --output_path "$OUT_DIR/valid_repos.csv" \
    --cache_dir "$CACHE_DIR/test_results"

java -cp build/libs/astmergeevaluation-all.jar \
    astmergeevaluation.FindMergeCommits \
    "$OUT_DIR/valid_repos.csv" \
    "$OUT_DIR/merges"

python3 src/python/merge_filter.py \
    --valid_repos_csv "$OUT_DIR/valid_repos.csv" \
    --merges_path "$OUT_DIR/merges/" \
    --output_dir "$OUT_DIR/merges_analyze/" \
    --cache_dir "$CACHE_DIR/merges"

python3 src/python/merge_tester.py \
    --valid_repos_csv "$OUT_DIR/valid_repos.csv" \
    --merges_path "$OUT_DIR/merges_analyze/" \
    --output_dir "$OUT_DIR/merges_tested/" \
    --n_merges "$N_MERGES" \
    --cache_dir "$CACHE_DIR/test_results"

python3 src/python/latex_output.py \
    --tested_merges_path "$OUT_DIR/merges_tested/" \
    --full_repos_csv "$REPOS_CSV" \
    --valid_repos_csv "$OUT_DIR/valid_repos.csv" \
    --n_merges "$N_MERGES" \
    --result_csv "$OUT_DIR/result.csv" \
    --all_merges_path "$OUT_DIR/merges/" \
    --merges_valid_path "$OUT_DIR/merges_valid/" \
    --output_dir "$OUT_DIR"
