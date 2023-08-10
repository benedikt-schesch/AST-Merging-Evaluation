#!/usr/bin/env bash

# usage: ./gitmerge-resolve.sh <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"
clone_dir=$1
branch1=$2
branch2=$3
strategy="-s resolve"
"$MERGE_SCRIPTS_DIR"/gitmerge.sh "$clone_dir" "$branch1" "$branch2" "$strategy"
status=$?

readarray -t files < <(grep -l -r '^\(<<<<<<<\||||||||\|>>>>>>>\) .merge_file_')

for file in "${files[@]}" ; do
  sed -i 's/^\(\(<<<<<<<\||||||||\|>>>>>>>\) .merge_file\)_[a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9]$/\1/' "$file"
done

exit "$status"
