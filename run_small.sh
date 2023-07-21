#!/usr/bin/env bash

# usage: ./run_small.sh [-i <machine_id> -n <num_machines>] [-d]
# Runs the stack on two small repos.
# The output appears in results-small/ .
# <machine_id> optional argument to specify the id of the current machine.
# <num_machine> optional argument to specify the total number of machines used.
# <diff> optional argument to specify whether to diff the merges.


set -e
set -o nounset

./run.sh input_data/repos_small.csv results-small 2 test_cache "$@"
