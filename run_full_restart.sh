#!/usr/bin/env bash

# Number of runs as arg
NUM_RUNS=$1

for i in $(seq 1 "$NUM_RUNS")
do
    echo "Run $i"
    ./run_full.sh
    make update-cache-results
    python3 src/python/delete_failed_trivial_merge_entries.py -y
    python3 src/python/delete_inconsistent_merge_results.py -y
    python3 src/python/delete_failed_cache_entries.py -y
done

make update-cache-results
./run_full -d
