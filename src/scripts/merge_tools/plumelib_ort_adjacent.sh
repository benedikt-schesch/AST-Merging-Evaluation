#!/usr/bin/env sh

# usage: ./plumelib_ort_adjacent.sh <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"
clone_dir=$1
branch1=$2
branch2=$3
git_strategy="-s ort"
plumelib_strategy="--only-adjacent"
"$MERGE_SCRIPTS_DIR"/merge_plumelib.sh "$clone_dir" "$branch1" "$branch2" "$git_strategy" "$plumelib_strategy"
