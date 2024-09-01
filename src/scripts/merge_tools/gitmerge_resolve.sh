#!/usr/bin/env bash

# usage: ./gitmerge_resolve.sh <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"
clone_dir=$1
branch1=$2
branch2=$3
strategy="-s resolve"
"$MERGE_SCRIPTS_DIR"/gitmerge.sh "$clone_dir" "$branch1" "$branch2" "$strategy"
status=$?

if [ "$status" -ne 0 ]; then
  echo "Removing filenames from conflict markers."
  cd "$clone_dir" || (echo "$0: cannot cd to $clone_dir" ; exit 2)
  readarray -t files < <(grep -l -r '^\(<<<<<<<\||||||||\|>>>>>>>\) .merge_file_')
  for file in "${files[@]}" ; do
    echo "Removing filenames from conflict markers in $file"
    sed -i 's/^\(\(<<<<<<<\||||||||\|>>>>>>>\) .merge_file\)_[a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9]$/\1/' "$file"
  done
fi


exit "$status"
