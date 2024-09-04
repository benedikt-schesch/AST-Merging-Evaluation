#!/bin/sh
# Run the code of a specific branch of this repository on a remote machine.
# Usage: ./run_remotely.sh <branch> <machine_ssh> <machine_id> <num_machines> <root_path_on_machine>
# <branch> is the branch to run
# <machine_ssh> is the ssh address of the machine
# <machine_id> is the id of the machine (0, 1, 2, ...)
# <num_machines> is the total number of machines
# <root_path_on_machine> is the path to the root of the code on the machine


# Check arguments
if [ "$#" -ne 5 ]; then
    echo "Usage: ./run_remotely.sh <branch> <machine_ssh> <machine_id> <num_machines> <root_path_on_machine>"
    exit 2
fi

BRANCH=$1
MACHINE_SSH=$2
MACHINE_ID=$3
NUM_MACHINES=$4
ROOT_PATH_ON_MACHINE=$5

echo "Running branch $BRANCH on machine $MACHINE_SSH with id $MACHINE_ID out of $NUM_MACHINES machines (ROOT PATH: $ROOT_PATH_ON_MACHINE)"
echo "Executing: ssh -t $MACHINE_SSH \"cd $ROOT_PATH_ON_MACHINE; pwd; killall screen; git checkout $BRANCH; git pull; conda activate AST; make clean-local; screen -m nice -n 10 ./run_combined.sh $MACHINE_ID $NUM_MACHINES\""

# Connect to machine and execute code using a screen session
ssh -t "$MACHINE_SSH" "cd $ROOT_PATH_ON_MACHINE; pwd; killall screen; git checkout $BRANCH; git pull; conda activate AST; make clean-local; screen -m nice -n 10 ./run_combined.sh $MACHINE_ID $NUM_MACHINES"
