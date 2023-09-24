#!/bin/bash
# Run the code of a specific branch of this repository on multiple remote machines.
# Usage: ./run_multiple_machines.sh <branch> <machine_address_path> <root_path_on_machine>
# <branch> is the branch to run
# <machine_address_path> is the path to a file containing the addresses of the machines (one address per line)
# <root_path_on_machine> is the path to the root of the code on the machine

# Check arguments
if [ "$#" -ne 3 ]; then
    echo "Usage: ./run_multiple_machines.sh <branch> <machine_address_path> <root_path_on_machine>"
    exit 1
fi

BRANCH="$1"
MACHINE_ADDRESS_PATH="$2"
ROOT_PATH_ON_MACHINE="$3"

# Read machine addresses from file
MACHINE_ADDRESSES=()
while IFS='' read -r line || [[ -n "$line" ]]; do
    MACHINE_ADDRESSES+=("$line")
done < "$MACHINE_ADDRESS_PATH"
NUM_MACHINES=${#MACHINE_ADDRESSES[@]}

# Check that the number of machines is at least 1
if [ "$NUM_MACHINES" -lt 1 ]; then
    echo "Error: number of machines is less than 1"
    exit 1
fi

# Check that machines are reachable
for i in "${!MACHINE_ADDRESSES[@]}"; do
    MACHINE_ADDRESS="${MACHINE_ADDRESSES[$i]}"
    echo "Checking if machine $i with address $MACHINE_ADDRESS is reachable"
    if ! ssh -o ConnectTimeout=1 "$MACHINE_ADDRESS" exit >/dev/null 2>&1; then
        echo "Error: machine $i with address $MACHINE_ADDRESS is not reachable"
        exit 1
    fi
done
echo "Success: all machines are reachable"

echo "Running branch $BRANCH on $NUM_MACHINES machines"
echo "Running on machines:" "${MACHINE_ADDRESSES[@]}"

for i in "${!MACHINE_ADDRESSES[@]}"; do
    MACHINE_ADDRESS="${MACHINE_ADDRESSES[$i]}"
    echo "Running on machine $i with address $MACHINE_ADDRESS"
    echo "Executing: gnome-terminal --tab -- bash -ic \"./src/scripts/utils/run_remotely.sh $BRANCH $MACHINE_ADDRESS $i $NUM_MACHINES $ROOT_PATH_ON_MACHINE; bash\""
    gnome-terminal --tab -- bash -ic "./src/scripts/utils/run_remotely.sh $BRANCH $MACHINE_ADDRESS $i $NUM_MACHINES $ROOT_PATH_ON_MACHINE; bash"
done
