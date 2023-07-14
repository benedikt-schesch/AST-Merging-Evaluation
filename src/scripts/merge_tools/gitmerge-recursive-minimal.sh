#!/usr/bin/env bash

# usage: ./gitmerge_recursive_minimal.sh <clone_dir> <branch-1> <branch-2>

MERGE_DIR=$(dirname "$0");
clone_dir=$1
branch1=$2
branch2=$3
strategy="-s recursive -Xdiff-algorithm=minimal"
eval "$MERGE_DIR/gitmerge.sh $clone_dir $branch1 $branch2 \"$strategy\""
