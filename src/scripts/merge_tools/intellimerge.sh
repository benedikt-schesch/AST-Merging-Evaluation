#!/usr/bin/env bash

# usage: ./intellimerge.sh <dir> <branch-1> <branch-2>
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

INTELLIMERGE=./jars/IntelliMerge-1.0.9-all.jar

dir=$1
branch1=$2
branch2=$3
temp_dir=".workdir/intelli_temp_$$/"
mkdir $temp_dir
wd=$(pwd)

# run intellimerge
java -jar $INTELLIMERGE -r "$dir" -b "$branch1" "$branch2" -o $temp_dir

# run git merge
cd "$dir"
git checkout "$branch1"
# collect initial counts of conflict markers
m1a=$(grep -ro "<<<<<<<" . | wc -l)
m2a=$(grep -ro "=======" . | wc -l)
m3a=$(grep -ro ">>>>>>>" . | wc -l)
git merge --no-edit "$branch2"

# move files
cd "$wd"
find $temp_dir -type f | while read -r f; do
    # construct paths
    suffix=${f#"$temp_dir"}
    mv "$f" "$dir$suffix"
done

# report conflicts
m1b=$(grep -ro "<<<<<<<" "$dir" | wc -l)
m2b=$(grep -ro "=======" "$dir" | wc -l)
m3b=$(grep -ro ">>>>>>>" "$dir" | wc -l)
if [ "$m1a" -ne "$m1b" ] && [ "$m2a" -ne "$m2b" ] && [ "$m3a" -ne "$m3b" ]; then
    rm -rf $temp_dir
    echo "Conflict"
    exit 1
fi
rm -rf $temp_dir
exit 0
