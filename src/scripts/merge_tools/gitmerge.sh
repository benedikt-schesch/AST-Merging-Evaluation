#!/bin/bash

# usage: ./gitmerge.sh <merge-dir> <branch-1> <branch-2>
# merges branch2 into branch1
# outputs result in-place to merge-dir

set -e
set -o nounset

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 MERGE_DIR BRANCH1 BRANCH2" >&2
  exit 1
fi

repo=$1
branch1=$2
branch2=$3
wd=$(pwd)

# perform merge
cd "$repo"
git checkout "$branch1"
git merge --no-edit "$branch2"

# report conflicts
retVal=$?
if [ $retVal -ne 0 ]; then
    echo "Conflict"
    git merge --abort
    cd "$wd"
    exit $retVal
fi

# go back to wd
cd "$wd"
