#!/usr/bin/env bash

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

clone_dir=$1
branch1=$2
branch2=$3

cd "$clone_dir" || { echo "$0: cannot cd to $clone_dir"; exit 2; }

# set up mergiraf driver
git config --local merge.mergiraf.name mergiraf
git config --local merge.mergiraf.driver "mergiraf merge --git %O %A %B -s %S -x %X -y %Y -p %P"
mergiraf languages --gitattributes >> .gitattributes

# perform merge
git checkout "$branch1" --force
git merge --no-edit "$branch2"
retVal=$?

# report conflicts
if [ $retVal -ne 0 ]; then
    echo "mergiraf.sh: Conflict"
fi

exit $retVal
