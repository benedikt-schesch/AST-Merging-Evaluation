#!/bin/bash

# This script edits files to remove conflict markers related to Java imports.
# Works on all files given on the command line; if none are given,
# works on all files in or under the current directory.

# This is not a git mergetool.  A git mergetool is given the base, parent 1, and
# parent 2 files, all without conflict markers.

if [ "$#" -eq 0 ] ; then
  readarray -t files < <(grep -l -r '^<<<<<<< HEAD' .)
else
  files=("$@")
fi

SCRIPTDIR="$(cd "$(dirname "$0")" && pwd -P)"

status=0

for file in "${files[@]}" ; do
  if ! "${SCRIPTDIR}"/resolve-import-conflicts-in-file.sh "$file" ; then
    status=1
  fi
done

exit $status
