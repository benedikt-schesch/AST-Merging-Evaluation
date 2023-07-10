#!/usr/bin/env bash

# usage: ./run_full.sh <machine_id> <num_machines>
# Runs the stack all the repositories
# The output appears in result/ .
# <machine_id> optional argument to specify the id of the current machine.
# <num_machine> optional argument to specify the total number of machines used.
# Warning: This takes days to run.

machine_id="${1:-0}"
num_machines="${2:-1}"

set -e
set -o nounset

./run.sh input_data/repos.csv results 20 cache "$machine_id" "$num_machines"
