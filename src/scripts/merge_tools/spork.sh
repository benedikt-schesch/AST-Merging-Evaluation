#!/bin/bash

# usage: ./spork.sh <dir> <branch-1> <branch-2>
# <dir> must contain a clone of a repository.
# Merges branch2 into branch1, in <dir>.
# Return code is 0 for merge success, 1 for merge failure.
# For merge failure, also outputs "Conflict".

set -e
set -o nounset

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 MERGE_DIR BRANCH1 BRANCH2" >&2
  exit 1
fi

SPORK=./jars/spork.jar
sporkfullpath=$(realpath $SPORK)

dir=$1
branch1=$2
branch2=$3
wd=$(pwd)

# set up spork driver
(echo "[merge \"spork\"]";
    echo "    name = spork";
    echo "    driver = java -jar $sporkfullpath --git-mode %A %O %B -o %A") >> "$dir/.git/config"
echo "*.java merge=spork" >> "$dir/.gitattributes"

# perform merge
cd "$dir"
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

exit 0
