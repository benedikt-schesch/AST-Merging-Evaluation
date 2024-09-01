#!/usr/bin/env sh

# usage: ./plumelib_intellimerge.sh <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"
clone_dir=$1
branch1=$2
branch2=$3
merge_script="intellimerge.sh"
plumelib_strategy=""
"$MERGE_SCRIPTS_DIR"/merge_script_then_plumelib.sh "$clone_dir" "$branch1" "$branch2" "$merge_script" "$plumelib_strategy"
