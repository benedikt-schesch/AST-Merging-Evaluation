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

PATH=$(pwd)/src/scripts/merge_tools/:$PATH
PATH=$(pwd)/src/scripts/merge_tools/merging/src/main/sh/:$PATH
export PATH

./src/scripts/merge_tools/merging/gradlew shadowJar

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

./gradlew -q assemble -g ../.gradle/

mkdir -p "$OUT_DIR"

# Delete all locks
if [ -d "$CACHE_DIR" ]; then
    find "$CACHE_DIR" -name "*.lock" -delete
fi
if [ -d "repos" ]; then
    find "repos/locks" -name "*.lock" -delete
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

# Sample 5*<n_merges> merges
read -ra merge_comparator_flags <<<"${comparator_flags}"
python3 src/python/merges_sampler.py \
    --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
    --merges_path "$OUT_DIR/merges/" \
    --output_dir "$OUT_DIR/merges_sampled/" \
    --n_merges "$((5 * "$N_MERGES"))" \
    "${merge_comparator_flags[@]}"

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

# Define an array for additional arguments
extra_args=()

if [ "$no_timing" = false ]; then
    python3 src/python/merge_runtime_measure.py \
        --repos_head_passes_csv "$OUT_DIR/local_repos.csv" \
        --merges "$OUT_DIR/merges_tested/" \
        --output_dir "$OUT_DIR/merges_timed/" \
        --n_sampled_timing 1 \
        --n_timings 3 \
        --cache_dir "$CACHE_DIR"
    extra_args+=(--timed_merges_path "$OUT_DIR/merges_timed/")
fi

python3 src/python/latex_output.py \
    --run_name "$RUN_NAME" \
    --merges_path "$OUT_DIR/merges/" \
    --tested_merges_path "$OUT_DIR/merges_tested/" \
    --analyzed_merges_path "$OUT_DIR/merges_analyzed/" \
    "${extra_args[@]}" \
    --full_repos_csv "$REPOS_CSV_WITH_HASHES" \
    --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
    --n_merges "$N_MERGES" \
    --output_dir "$OUT_DIR"
