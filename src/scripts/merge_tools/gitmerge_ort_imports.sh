#!/usr/bin/env sh

# usage: ./gitmerge_ort_imports.sh <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"
clone_dir=$1
branch1=$2
branch2=$3
strategy="-s ort"
if "$MERGE_SCRIPTS_DIR"/gitmerge.sh "$clone_dir" "$branch1" "$branch2" "$strategy" "no-git-merge-abort" ; then
  exit
fi

(cd "$clone_dir" && "$MERGE_SCRIPTS_DIR"/resolve-import-conflicts)
