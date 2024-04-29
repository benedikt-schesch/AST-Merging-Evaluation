#!/usr/bin/env bash

# usage: ./run.sh <repo_list> <run_name> <n_merges> [-i <machine_id> -n <num_machines>] [-t] [-ot] [-nt] [-op]
# <repo_list> list of repositories in csv formart with a column
#     "repository" that has the format "owner/reponame" for each repository.
# <run_name> name of the dataset.
# <n_merges> number of merges to sample for each repository.
# <machine_id> optional argument to specify the id of the current machine.
# <num_machine> optional argument to specify the total number of machines used.
# -t optional argument to include trivial merges.
# -ot optional argument to only use trivial merges.
# -nt optional argument to not measure the time of the merges.
# -op optional argument to only do plotting and table generation.
# The output appears in results/<run_name>.


set -e
set -o nounset

REPOS_CSV="$1"
RUN_NAME="$2"
OUT_DIR="results/$RUN_NAME"
N_MERGES=$3
CACHE_DIR="${4}"

# Do not run this script on MacOS.
backend=$(uname -s)
if [ "$backend" = "Darwin" ]; then
    echo "Error: MacOS is not supported. Please run the script on a Linux machine. This is due to the use of readarray in certain merge tools."
    exit 1
fi

comparator_flags=""
no_timing=false
only_plotting=false
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
    comparator_flags="$comparator_flags --include_trivial_merges"
    ;;
    -ot | --only_trivial_merges)
    comparator_flags="$comparator_flags --only_trivial_merges"
    ;;
    -nt | --no_timing)
    no_timing=true
    ;;
    -op | --only_plotting)
    only_plotting=true
    ;;
  esac
  shift
done

# Check if src/scripts/merge_tools/merging is present
if [ ! -d src/scripts/merge_tools/merging ]; then
    echo "Error: src/scripts/merge_tools/merging is missing. This is a submodule that is required for the script to run."
    echo "Please run 'git submodule update --init' to fetch the submodule."
    exit 1
fi

PATH=$(pwd)/src/scripts/merge_tools:$PATH
PATH=$(pwd)/src/scripts/merge_tools/merging/src/main/sh:$PATH
export PATH

echo "Checking for custom merge drivers in global configuration..."
merge_drivers=$(git config --global --get-regexp '^merge\..*\.driver$' || echo "No merge drivers set")

if [ "$merge_drivers" == "No merge drivers set" ]; then
    echo "No custom merge drivers found in global configuration. Proceeding with the evaluation."
    # Include other commands to continue the script here
else
    echo "Error: Custom merge drivers are set in global configuration."
    echo "Please unset them before running the evaluation."
    echo "Merge driver found: $merge_drivers"
    exit 1
fi

# Check if cache.tar exists and cache is missing
if [ -f cache.tar ] && [ ! -d cache ]; then
    echo "Decompressing cache.tar"
    # make decompress-cache
fi

mvn -v | head -n 1 | cut -c 14-18 | grep -q 3.9. || { echo "Maven 3.9.* is required"; mvn -v; echo "PATH=$PATH"; exit 1; }
if [ -z "${JAVA8_HOME:+isset}" ] ; then echo "JAVA8_HOME is not set"; exit 1; fi
if [ -z "${JAVA11_HOME:+isset}" ] ; then echo "JAVA11_HOME is not set"; exit 1; fi
if [ -z "${JAVA17_HOME:+isset}" ] ; then echo "JAVA17_HOME is not set"; exit 1; fi

if [ -z "${machine_id:+isset}" ] ; then machine_id=0; fi
if [ -z "${num_machines:+isset}" ] ; then num_machines=1; fi

export JAVA_HOME=$JAVA17_HOME
if [ ! -f ./src/scripts/merge_tools/merging/.git ] ; then
    git submodule update --init --recursive
fi
git submodule update --recursive --remote
(cd ./src/scripts/merge_tools/merging && ./gradlew shadowJar)

echo "Machine ID: $machine_id"
echo "Number of machines: $num_machines"
echo "Output directory: $OUT_DIR"
echo "Options: $comparator_flags"

# Add a _with_hashes to the $REPOS_CSV
REPOS_CSV_WITH_HASHES="${REPOS_CSV%.*}_with_hashes.csv"

if [ "$only_plotting" = true ]; then
    python3 src/python/latex_output.py \
        --run_name "$RUN_NAME" \
        --merges_path "$OUT_DIR/merges/" \
        --tested_merges_path "$OUT_DIR/merges_tested/" \
        --analyzed_merges_path "$OUT_DIR/merges_analyzed/" \
        --full_repos_csv "$REPOS_CSV_WITH_HASHES" \
        --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
        --n_merges "$N_MERGES" \
        --output_dir "$OUT_DIR"
    exit 0
fi

export JAVA_HOME=$JAVA11_HOME
./gradlew -q assemble -g ../.gradle/

mkdir -p "$OUT_DIR"

# Delete all locks in cache
if [ -d "$CACHE_DIR" ]; then
    find "$CACHE_DIR" -name "*.lock" -delete
fi

# Delete .workdir
rm -rf .workdir

python3 src/python/delete_cache_placeholders.py \
    --cache_dir "$CACHE_DIR"

python3 src/python/write_head_hashes.py \
    --repos_csv "$REPOS_CSV" \
    --output_path "$REPOS_CSV_WITH_HASHES"

python3 src/python/test_repo_heads.py \
    --repos_csv_with_hashes "$REPOS_CSV_WITH_HASHES" \
    --output_path "$OUT_DIR/repos_head_passes.csv" \
    --cache_dir "$CACHE_DIR"

java -cp build/libs/astmergeevaluation-all.jar \
    astmergeevaluation.FindMergeCommits \
    "$OUT_DIR/repos_head_passes.csv" \
    "$OUT_DIR/merges"

# Calculate the number of merges
total_merges=$((5 * N_MERGES))

# Ensure comparator_flags is set, but default to an empty array if not
if [[ -n "${comparator_flags}" ]]; then
    read -ra merge_comparator_flags <<< "${comparator_flags}"
    python3 src/python/merges_sampler.py \
        --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
        --merges_path "$OUT_DIR/merges/" \
        --output_dir "$OUT_DIR/merges_sampled/" \
        --n_merges "$total_merges" \
        "${merge_comparator_flags[@]}"
else
    echo "Warning: 'comparator_flags' is empty, continuing without additional flags."
    python3 src/python/merges_sampler.py \
        --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
        --merges_path "$OUT_DIR/merges/" \
        --output_dir "$OUT_DIR/merges_sampled/" \
        --n_merges "$total_merges"
fi

python3 src/python/split_repos.py \
    --repos_csv "$OUT_DIR/repos_head_passes.csv" \
    --machine_id "$machine_id" \
    --num_machines "$num_machines" \
    --output_file "$OUT_DIR/local_repos.csv"

python3 src/python/merge_analyzer.py \
    --repos_head_passes_csv "$OUT_DIR/local_repos.csv" \
    --merges_path "$OUT_DIR/merges_sampled/" \
    --output_dir "$OUT_DIR/merges_analyzed/" \
    --n_sampled_merges "$N_MERGES" \
    --cache_dir "$CACHE_DIR"

python3 src/python/merge_tester.py \
    --repos_head_passes_csv "$OUT_DIR/local_repos.csv" \
    --merges_path "$OUT_DIR/merges_analyzed/" \
    --output_dir "$OUT_DIR/merges_tested/" \
    --cache_dir "$CACHE_DIR"

if [ "$no_timing" = false ]; then
    python3 src/python/merge_runtime_measure.py \
        --repos_head_passes_csv "$OUT_DIR/local_repos.csv" \
        --merges "$OUT_DIR/merges_tested/" \
        --output_dir "$OUT_DIR/merges_timed/" \
        --n_sampled_timing 1 \
        --n_timings 3 \
        --cache_dir "$CACHE_DIR"

    python3 src/python/latex_output.py \
        --run_name "$RUN_NAME" \
        --merges_path "$OUT_DIR/merges/" \
        --tested_merges_path "$OUT_DIR/merges_tested/" \
        --analyzed_merges_path "$OUT_DIR/merges_analyzed/" \
        --timed_merges_path "$OUT_DIR/merges_timed/" \
        --full_repos_csv "$REPOS_CSV_WITH_HASHES" \
        --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
        --n_merges "$N_MERGES" \
        --output_dir "$OUT_DIR"
fi

python3 src/python/latex_output.py \
    --run_name "$RUN_NAME" \
    --merges_path "$OUT_DIR/merges/" \
    --tested_merges_path "$OUT_DIR/merges_tested/" \
    --analyzed_merges_path "$OUT_DIR/merges_analyzed/" \
    --full_repos_csv "$REPOS_CSV_WITH_HASHES" \
    --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
    --n_merges "$N_MERGES" \
    --output_dir "$OUT_DIR"
