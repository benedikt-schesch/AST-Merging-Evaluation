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
MERGIRAF_VERSION="0.4.0"

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

# Add a _with_hashes to the $REPOS_CSV
REPOS_CSV_WITH_HASHES="${REPOS_CSV%.*}_with_hashes.csv"

make clean-workdir

# shellcheck disable=SC2086
run_latex_output() {
    local timing_option="$1"
    python3 src/python/latex_output.py \
        --run_name "$RUN_NAME" \
        --merges_path "$OUT_DIR/merges/" \
        --tested_merges_path "$OUT_DIR/merges_tested/" \
        --analyzed_merges_path "$OUT_DIR/merges_analyzed/" \
        $timing_option \
        --full_repos_csv "$REPOS_CSV_WITH_HASHES" \
        --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
        --n_merges "$N_MERGES" \
        --output_dir "$OUT_DIR" \
        --test_cache_dir "$CACHE_DIR/test_cache" \
        --manual_override_csv "results/manual_override.csv"
}

if [ "$only_plotting" = true ]; then
    if [ "$no_timing" = true ]; then
        run_latex_output ""
    else
        run_latex_output "--timed_merges_path $OUT_DIR/merges_timed/"
    fi
    exit 0
fi

PATH=$(pwd)/src/scripts/merge_tools:$PATH
PATH=$(pwd)/src/scripts/merge_tools/merging/src/main/sh:$PATH
export PATH

# Empty config file
GIT_CONFIG_GLOBAL=$(pwd)/.gitconfig
export GIT_CONFIG_GLOBAL

# Check if cache.tar.gz exists and cache is missing
if [ -f cache.tar.gz ] && [ ! -d cache ]; then
    read -r -p "cache.tar.gz found and cache directory missing. Do you want to decompress? (y/n) " answer
    if [ "$answer" = "y" ]; then
        echo "Decompressing cache.tar.gz"
        make decompress-cache
    else
        echo "Decompression aborted."
    fi
fi

# Check if cache_without_logs.tar.gz exists and cache is missing
if [ -f cache_without_logs.tar.gz ] && [ ! -d cache_without_logs ]; then
    read -r -p "cache_without_logs.tar.gz found and cache_without_logs directory missing. Do you want to decompress? (y/n) " answer
    if [ "$answer" = "y" ]; then
        echo "Decompressing cache_without_logs.tar.gz"
        make decompress-cache-without-logs
    else
        echo "Decompression aborted."
    fi
fi

# Check if git version is sufficient
MIN_GIT_VERSION="2.44"
INSTALLED_VERSION=$(git --version | awk '{print $3}')

if [ "$(printf '%s\n' "$MIN_GIT_VERSION" "$INSTALLED_VERSION" | sort -V | head -n1)" = "$MIN_GIT_VERSION" ]; then
    echo "Git version $INSTALLED_VERSION is sufficient (>= $MIN_GIT_VERSION)."
else
    echo "Error: Git version $INSTALLED_VERSION is less than $MIN_GIT_VERSION."
    exit 1
fi


mvn -v | head -n 1 | cut -c 14-18 | grep -q 3.9. || { echo "Maven 3.9.* is required"; mvn -v; echo "PATH=$PATH"; exit 2; }
if [ -z "${JAVA8_HOME:+isset}" ] ; then echo "JAVA8_HOME is not set"; exit 2; fi
if [ -z "${JAVA11_HOME:+isset}" ] ; then echo "JAVA11_HOME is not set"; exit 2; fi
if [ -z "${JAVA17_HOME:+isset}" ] ; then echo "JAVA17_HOME is not set"; exit 2; fi

if [ -z "${machine_id:+isset}" ] ; then machine_id=0; fi
if [ -z "${num_machines:+isset}" ] ; then num_machines=1; fi

if [ ! -f ./src/scripts/merge_tools/merging/.git ] ; then
    git submodule update --init --recursive
fi

# Check if mergiraf is installed and matches the required version
if ! mergiraf --version 2>/dev/null | grep -q "mergiraf $MERGIRAF_VERSION"; then
  echo "Installing mergiraf version $MERGIRAF_VERSION..."
  cargo install --locked mergiraf --version "$MERGIRAF_VERSION"
else
  echo "mergiraf version $MERGIRAF_VERSION is already installed."
fi

(
  cd ./src/scripts/merge_tools/merging
  export JAVA_HOME=$GRAALVM_HOME
  export PATH="$JAVA_HOME/bin:$PATH"
  ./gradlew -q nativeCompile
)

echo "Machine ID: $machine_id"
echo "Number of machines: $num_machines"
echo "Output directory: $OUT_DIR"
echo "Options: $comparator_flags"

JAVA_HOME="$JAVA11_HOME" ./gradlew -q assemble -g ../.gradle/

mkdir -p "$OUT_DIR"

# Delete all locks
if [ -d "$CACHE_DIR" ]; then
    find "$CACHE_DIR" -name "*.lock" -delete
fi
REPOS_PATH=${AST_REPOS_PATH:-repos}
if [ -d "$REPOS_PATH" ]; then
    find "$REPOS_PATH/locks" -name "*.lock" -delete
fi

echo "run.sh: about to run delete_cache_placeholders.py"
python3 src/python/utils/delete_cache_placeholders.py \
    --cache_dir "$CACHE_DIR"

echo "run.sh: about to run write_head_hashes.py"
python3 src/python/write_head_hashes.py \
    --repos_csv "$REPOS_CSV" \
    --output_path "$REPOS_CSV_WITH_HASHES"

echo "run.sh: about to run test_repo_heads.py"
python3 src/python/test_repo_heads.py \
    --repos_csv_with_hashes "$REPOS_CSV_WITH_HASHES" \
    --output_path "$OUT_DIR/repos_head_passes.csv" \
    --cache_dir "$CACHE_DIR"

echo "run.sh: about to run FindMergeCommits"
JAVA_HOME="${JAVA17_HOME}" "${JAVA17_HOME}"/bin/java -cp build/libs/astmergeevaluation-all.jar \
    astmergeevaluation.FindMergeCommits \
    "$OUT_DIR/repos_head_passes.csv" \
    "$OUT_DIR/merges"

# Calculate the number of merges
total_merges=$((5 * N_MERGES))

# Ensure comparator_flags is set, but default to an empty array if not
echo "run.sh: about to run merges_sampler.py"
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

echo "run.sh: about to run merge_analyzer.py"
python3 src/python/merge_analyzer.py \
    --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
    --merges_path "$OUT_DIR/merges_sampled/" \
    --output_dir "$OUT_DIR/merges_analyzed/" \
    --n_sampled_merges "$N_MERGES" \
    --cache_dir "$CACHE_DIR"

echo "run.sh: about to run merge_tester.py"
python3 src/python/merge_tester.py \
    --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
    --merges_path "$OUT_DIR/merges_analyzed/" \
    --output_dir "$OUT_DIR/merges_tested/" \
    --cache_dir "$CACHE_DIR"

if [ "$no_timing" = false ]; then
    echo "run.sh: about to run merge_runtime_measure.py"
    python3 src/python/merge_runtime_measure.py \
        --repos_head_passes_csv "$OUT_DIR/repos_head_passes.csv" \
        --merges "$OUT_DIR/merges_tested/" \
        --output_dir "$OUT_DIR/merges_timed/" \
        --n_sampled_timing 1 \
        --n_timings 3 \
        --cache_dir "$CACHE_DIR"

    echo "run.sh: about to run run_latex_output"
    run_latex_output "--timed_merges_path $OUT_DIR/merges_timed/"
else
    echo "run.sh: about to run run_latex_output"
    run_latex_output ""
fi
