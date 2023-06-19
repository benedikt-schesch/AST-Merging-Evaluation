#!/usr/bin/env bash

# usage: ./spork.sh <clone_dir> <branch-1> <branch-2>
# <clone_dir> must contain a clone of a repository.
# Merges branch2 into branch1, in <clone_dir>.
# Return code is 0 for merge success, 1 for merge failure.
# For merge failure, also outputs "Conflict" and aborts the merge.

set -e
set -o nounset

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 MERGE_DIR BRANCH1 BRANCH2" >&2
  exit 1
fi

SCRIPT_PATH=$(dirname "$0"); SCRIPT_PATH=$(eval "cd \"$SCRIPT_PATH\" && pwd")
ROOT_PATH=$(realpath "${SCRIPT_PATH}/../../../")
spork_relativepath=jars/spork.jar
spork_fullpath="${ROOT_PATH}/${spork_relativepath}"

# If file ${spork_fullpath} does not exist, create it.
if [ ! -f "${spork_fullpath}" ]; then
    make -C "${ROOT_PATH}" "${spork_relativepath}"
fi

clone_dir=$1
branch1=$2
branch2=$3

# set up spork driver
(echo "[merge \"spork\"]";
    echo "    name = spork";
    echo "    driver = java -jar $spork_fullpath --git-mode %A %O %B -o %A") >> "$clone_dir/.git/config"
echo "*.java merge=spork" >> "$clone_dir/.gitattributes"

# perform merge
pushd "$clone_dir"
git checkout "$branch1" --force
git merge --no-edit "$branch2"
retVal=$?

# report conflicts
if [ $retVal -ne 0 ]; then
    echo "Conflict"
    git merge --abort
fi

popd
exit $retVal
