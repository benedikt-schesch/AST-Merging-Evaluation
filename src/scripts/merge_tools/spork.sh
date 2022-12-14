#!/bin/bash

# usage: ./spork.sh <merge-dir> <branch-1> <branch-2>
# merges branch2 into branch1
# outputs result in-place to merge-dir
SPORK=./jars/spork.jar
repo=$1
branch1=$2
branch2=$3
wd=$(pwd)
sporkfullpath=$(realpath $SPORK)
cd $repo

# set up spork driver
echo "[merge \"spork\"]" >> .git/config
    echo "    name = spork" >> .git/config
    echo "    driver = java -jar $sporkfullpath --git-mode %A %O %B -o %A" >> .git/config
echo "*.java merge=spork" >> .gitattributes

# perform merge
git checkout $branch1
git merge --no-edit $branch2

# report conflicts
retVal=$?
if [ $retVal -ne 0 ]; then
    echo "Conflict"
    git merge --abort
    cd $wd
    exit $retVal
fi

# go back to wd
cd $wd
exit 0
