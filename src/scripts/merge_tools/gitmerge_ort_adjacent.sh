#!/usr/bin/env sh

# usage: ./gitmerge_ort_adjacent.sh <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"
clone_dir=$1
branch1=$2
branch2=$3
strategy="-s ort"
if "$MERGE_SCRIPTS_DIR"/gitmerge.sh "$clone_dir" "$branch1" "$branch2" "$strategy"; then
  exit 0
fi

cd "$clone_dir" || exit 1
if ! "$MERGE_SCRIPTS_DIR"/resolve-adjacent-conflicts; then
  echo "gitmerge_ort_adjacent.sh: Conflict"
  exit 1
fi

exit 0
