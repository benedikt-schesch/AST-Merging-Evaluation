#!/usr/bin/env sh

# usage: ./gitmerge_ort_imports.sh <clone_dir> <branch-1> <branch-2>

clone_dir=$1
branch1=$2
branch2=$3
strategy="-s ort"

export JAVA_HOME="$JAVA17_HOME"

cd "$clone_dir" || exit 1

git checkout "$branch1" --force

attributes_file=".git/info/attributes"
echo "*.java merge=merge-java" >> "$attributes_file"
git config --local merge.merge-java.name "Merge Java files"
git config --local merge.merge-java.driver 'java-merge-driver.sh "%A" "%O" "%B"'

git merge --no-edit "$strategy" "$branch2"
retVal=$?

# report conflicts
if [ "$retVal" -ne 0 ]; then
    echo "Conflict"
fi

exit "$retVal"
