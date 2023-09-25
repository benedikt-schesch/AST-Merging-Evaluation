#!/usr/bin/env sh

# usage: ./gitmerge-ort.sh <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"
clone_dir=$1
branch1=$2
branch2=$3
strategy="-s ort"
"$MERGE_SCRIPTS_DIR"/gitmerge.sh "$clone_dir" "$branch1" "$branch2" "$strategy" "no-git-merge-abort"
status=$?

if ! "$status" ; then
  (cd "$clone_dir" && "$MERGE_SCRIPTS_DIR"/resolve-import-conflicts)

  # From https://stackoverflow.com/questions/41246415/
  status=$(git diff --exit-code -S '<<<<<<< HEAD' -S "=======" -S ">>>>>>> $(git name-rev --name-only MERGE_HEAD)" HEAD)

  git merge --abort
fi

exit "$status"
