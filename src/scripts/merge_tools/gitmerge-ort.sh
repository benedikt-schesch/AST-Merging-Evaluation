#!/usr/bin/env sh

# usage: ./gitmerge-ort.sh <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(dirname "$0")"
clone_dir=$1
branch1=$2
branch2=$3
strategy="-s ort"
"$MERGE_SCRIPTS_DIR"/gitmerge.sh "$clone_dir" "$branch1" "$branch2" "$strategy"
