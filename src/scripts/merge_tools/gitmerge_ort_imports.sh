#!/usr/bin/env sh

# usage: ./gitmerge_ort_imports.sh <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"
clone_dir=$1
branch1=$2
branch2=$3
strategy="-s ort"
if "$MERGE_SCRIPTS_DIR"/gitmerge.sh "$clone_dir" "$branch1" "$branch2" "$strategy"; then
  exit 0
fi

cd "$clone_dir" || exit 1
"$MERGE_SCRIPTS_DIR"/resolve-import-conflicts;

# Detect conflicts using Git commands
conflict_files=$(git diff --name-only --diff-filter=U)

if [ -n "$conflict_files" ]; then
    echo "Conflict detected in the following files:"
    echo "$conflict_files"
    exit 1
fi

echo "No conflicts detected."
exit 0
