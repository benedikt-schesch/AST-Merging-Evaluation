#!/bin/bash

# usage: ./run_small.sh
# Runs the stack on two small repos.
# The output appears in small/ .
# <machine_id> optional argument to specify the id of the current machine.
# <num_machine> optional argument to specify the total number of machines used.

machine_id="${1:-0}"
num_machines="${2:-1}"

set -e
set -o nounset

./run.sh input_data/repos_cf.csv cf 2 test_cache "$machine_id" "$num_machines"
