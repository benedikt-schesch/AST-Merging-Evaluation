#!/usr/bin/env sh

# usage: <scriptname> [--verbose] <clone_dir> <branch-1> <branch-2>
# <clone_dir> must contain a clone of a repository.
# Merges branch2 into branch1, in <clone_dir>.
# Return code is 0 for merge success, 1 for merge failure, 2 for script failure.
# For merge failure, also outputs "Conflict" and aborts the merge.

set -o nounset

verbose=
if [ "$1" = "--verbose" ] ; then
  # shellcheck disable=SC2034 # unused
  verbose="$1"
  shift
fi

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 [--verbose] CLONE_DIR BRANCH1 BRANCH2" >&2
  exit 2
fi

# Kill all Java processes that are running for over an hour (to avoid memory leaks).
# Spork tends to create Java processes that don't terminate even when the parent process is killed.
killall -9 java --older-than 1h

SCRIPT_PATH="$(dirname "$0")"; SCRIPT_PATH="$(eval "cd \"$SCRIPT_PATH\" && pwd")"
ROOT_PATH="$(realpath "${SCRIPT_PATH}/../../../")"
spork_relativepath=jars/spork.jar
spork_absolutepath="${ROOT_PATH}/${spork_relativepath}"

clone_dir=$1
branch1=$2
branch2=$3

cd "$clone_dir" || { echo "$0: cannot cd to $clone_dir"; exit 2; }

# Print the Java version.
echo "Java version:"
java -version


# set up spork driver
git config --local merge.spork.name "spork"
git config --local merge.spork.driver "java -jar $spork_absolutepath --logging --git-mode %A %O %B -o %A"

# print git config
echo "*.java merge=spork" >> .gitattributes

# perform merge
echo "Current git config:"
git config --list

git checkout "$branch1" --force
git merge --no-edit "$branch2"
retVal=$?

# report conflicts
if [ $retVal -ne 0 ]; then
    echo "spork.sh: Conflict"
fi

exit $retVal
