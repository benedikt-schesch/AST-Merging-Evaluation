#!/usr/bin/env sh

# usage: <scriptname> [--verbose] <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"


if [ "$1" = "--verbose" ] ; then
  shift
fi

clone_dir=$1
branch1=$2
branch2=$3
git_strategy="-s ort"
"$MERGE_SCRIPTS_DIR"/openaiapi_merge.sh "$clone_dir" "$branch1" "$branch2" "$git_strategy" deepseek-ai/DeepSeek-R1
