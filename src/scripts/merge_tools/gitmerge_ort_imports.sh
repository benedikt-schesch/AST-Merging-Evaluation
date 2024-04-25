#!/usr/bin/env sh

# usage: ./gitmerge_ort_imports.sh <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"
clone_dir=$1
branch1=$2
branch2=$3
strategy="-s ort"

export JAVA_HOME="$JAVA17_HOME"

cd "$clone_dir" || exit 1

attributes_file=".git/info/attributes"
echo "*.java merge=merge-java" >> "$attributes_file"

git config --local merge.merge-java.name "Merge Java files"
git config --local merge.merge-java.driver 'java-merge-driver.sh "%A" "%O" "%B"'
"$MERGE_SCRIPTS_DIR"/gitmerge.sh "$clone_dir" "$branch1" "$branch2" "$strategy"
