#!/bin/bash

# usage: ./intellmerge.sh <merge-dir> <branch1> <branch2>
INTELLIMERGE=./jars/IntelliMerge-1.0.9-all.jar
repo=$1
branch1=$2
branch2=$3
wd=$(pwd)

# run intellimerge
java -jar $INTELLIMERGE -r $repo -b $branch1 $branch2 -o temp

# run git merge
cd $repo
git checkout $branch1
# collect initial counts of conflict markers
m1a=$(grep -ro "<<<<<<<" . | wc -l)
m2a=$(grep -ro "=======" . | wc -l)
m3a=$(grep -ro ">>>>>>>" . | wc -l)
git merge --no-edit $branch2

# move files
cd $wd
find temp -type f|while read f; do
    # construct paths
    suffix=${f#"temp"}
    mv $f $repo$suffix
done

# report conflicts
m1b=$(grep -ro "<<<<<<<" $repo | wc -l)
m2b=$(grep -ro "=======" $repo | wc -l)
m3b=$(grep -ro ">>>>>>>" $repo | wc -l)
if [ $m1a -ne $m1b ] && [ $m2a -ne $m2b ] && [ $m3a -ne $m3b ]; then
    echo "Conflict"
    exit 1
fi
exit 0
