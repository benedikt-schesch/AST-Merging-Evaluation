#!/usr/bin/env sh

# usage: ./gitmerge_recursive_histogram.sh <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"
clone_dir=$1
branch1=$2
branch2=$3
strategy="-s recursive -Xdiff-algorithm=histogram"
"$MERGE_SCRIPTS_DIR"/gitmerge.sh "$clone_dir" "$branch1" "$branch2" "$strategy"
if [ $? -ne 0 ] ; then
  exit 1
fi
