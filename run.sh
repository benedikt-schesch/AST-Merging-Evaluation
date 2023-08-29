#!/usr/bin/env bash

# usage: ./run.sh <repo_list> <output_folder> <n_merges> [-i <machine_id> -n <num_machines>] [-d]
# <repo_list> list of repositories in csv formart with a column
#     "repository" that has the format "owner/reponame" for each repository.
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

merge_tester_flags=""
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
    -t | --include_trivial_merges)
    merge_tester_flags="$merge_tester_flags --include_trivial_merges"
    ;;
    -ot | --only_trivial_merges)
    merge_tester_flags="$merge_tester_flags --only_trivial_merges"
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
echo "Merge tester options: $merge_tester_flags"

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

python3 src/python/test_repo_head.py \
    --repos_csv_with_hashes "$OUT_DIR/local_repos.csv" \
    --output_path "$OUT_DIR/repos_head_passes.csv" \
    --cache_dir "$CACHE_DIR"

java -cp build/libs/astmergeevaluation-all.jar \
    astmergeevaluation.FindMergeCommits \
    "$OUT_DIR/repos_head_passes.csv" \
    "$OUT_DIR/merges"

python3 src/python/merge_tools_comparator.py \
    --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
    --merges_path "$OUT_DIR/merges/" \
    --output_dir "$OUT_DIR/merges_compared/" \
    --cache_dir "$CACHE_DIR"

read -ra merge_tester_options <<<"${merge_tester_flags}"
python3 src/python/merge_tester.py \
    --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
    --merges_path "$OUT_DIR/merges_compared/" \
    --output_dir "$OUT_DIR/merges_tested/" \
    --cache_dir "$CACHE_DIR" \
    "${merge_tester_options[@]}"

python3 src/python/merge_differ.py \
    --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
    --merges_path "$OUT_DIR/merges_tested" \
    --cache_dir "$CACHE_DIR"

python3 src/python/latex_output.py \
    --merges_path "$OUT_DIR/merges/" \
    --tested_merges_path "$OUT_DIR/merges_tested/" \
    --full_repos_csv "$REPOS_CSV" \
    --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
    --n_merges "$N_MERGES" \
    --output_dir "$OUT_DIR"
