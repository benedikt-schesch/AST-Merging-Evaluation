#!/usr/bin/env sh

# usage: <scriptname> [--verbose] <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"

verbose=
if [ "$1" = "--verbose" ] ; then
  verbose="$1"
  shift
fi

clone_dir=$1
branch1=$2
branch2=$3
git_strategy="-s recursive -Xdiff-algorithm=histogram"
plumelib_strategy=""
# shellcheck disable=SC2086 # '$verbose' should not be quoted
"$MERGE_SCRIPTS_DIR"/merge_git_then_plumelib.sh $verbose "$clone_dir" "$branch1" "$branch2" "$git_strategy" "$plumelib_strategy"
