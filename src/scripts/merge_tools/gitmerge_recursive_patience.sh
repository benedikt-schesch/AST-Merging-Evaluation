#!/usr/bin/env sh

# usage: ./gitmerge_recursive_patience.sh <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"
clone_dir=$1
branch1=$2
branch2=$3
git_strategy="-s recursive -Xdiff-algorithm=patience"
"$MERGE_SCRIPTS_DIR"/gitmerge.sh "$clone_dir" "$branch1" "$branch2" "$git_strategy"
