#!/usr/bin/env bash

# usage: ./gitmerge.sh <clone_dir> <branch-1> <branch-2> <strategy>
# <clone_dir> must contain a clone of a repository.
# <strategy> is the string to the follow the -s option to git merge,
# including anything passed through -X
# Merges branch2 into branch1, in <clone_dir>, using merge strategy <strategy>.
# Return code is 0 for merge success, 1 for merge failure.
# For merge failure, also outputs "Conflict" and aborts the merge.

set -e
set -o nounset

if [ "$#" -ne 4 ]; then
  echo "Usage: $0 MERGE_DIR BRANCH1 BRANCH2 STRATEGY" >&2
  exit 1
fi

clone_dir=$1
branch1=$2
branch2=$3
strategy=$4

# perform merge
pushd "$clone_dir"
git checkout "$branch1" --force
echo "Running: git merge --no-edit \"$branch2\" $strategy"
eval "git merge --no-edit \"$branch2\" $strategy"
retVal=$?

# report conflicts
if [ $retVal -ne 0 ]; then
    echo "Conflict"
    git merge --abort
fi

popd

exit $retVal
