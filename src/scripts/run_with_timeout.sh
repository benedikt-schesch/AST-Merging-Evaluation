#!/bin/bash
# usage: ./run_with_timeout.sh <timeout_in_seconds> <command>
# Run a command with a timeout. The exit status is 0 for success, 124 for timeout, and 1 for failure.

# Check if the correct number of arguments was provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <timeout_in_seconds> <command>"
    exit 1
fi

# Read the timeout and command from arguments
TIMEOUT=$1
shift
COMMAND=$*

# Function to run the command with a timeout
run_command_with_timeout() {
    # shellcheck disable=SC2086
    timeout --kill-after=10 "$TIMEOUT" $COMMAND
    local STATUS=$?

    # Check if the command timed out
    if [ $STATUS -eq 124 ]; then
        echo "The command timed out after ${TIMEOUT} seconds."
    elif [ $STATUS -ne 0 ]; then
        echo "The command failed with status $STATUS."
    else
        echo "The command completed successfully."
    fi

    return $STATUS
}

# Execute the function
run_command_with_timeout
