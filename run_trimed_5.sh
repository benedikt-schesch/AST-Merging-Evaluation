#!/usr/bin/env bash

# usage: ./run_combined.sh [-i <machine_id> -n <num_machines>] [-d]
# Runs the stack all the repositories
# The output appears in result/ .
# <machine_id> optional argument to specify the id of the current machine.
# <num_machine> optional argument to specify the total number of machines used.
# <diff> optional argument to specify whether to diff the merges.
# Warning: This takes days to run.


set -e
set -o nounset

./run.sh input_data/repos_combined.csv combined_trimed_5 5 cache "$@"
