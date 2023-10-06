#!/usr/bin/env sh

# usage: ./spork.sh <clone_dir> <branch-1> <branch-2>
# <clone_dir> must contain a clone of a repository.
# Merges branch2 into branch1, in <clone_dir>.
# Return code is 0 for merge success, 1 for merge failure.
# For merge failure, also outputs "Conflict" and aborts the merge.

set -e
set -o nounset

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 MERGE_SCRIPTS_DIR BRANCH1 BRANCH2" >&2
  exit 1
fi

SCRIPT_PATH="$(dirname "$0")"; SCRIPT_PATH="$(eval "cd \"$SCRIPT_PATH\" && pwd")"
ROOT_PATH="$(realpath "${SCRIPT_PATH}/../../../")"
spork_relativepath=jars/spork.jar
spork_absolutepath="${ROOT_PATH}/${spork_relativepath}"

clone_dir=$1
branch1=$2
branch2=$3

# set up spork driver
(echo "[merge \"spork\"]";
    echo "    name = spork";
    echo "    driver = java -jar $spork_absolutepath --git-mode %A %O %B -o %A") >> "$clone_dir/.git/config"
echo "*.java merge=spork" >> "$clone_dir/.gitattributes"

# perform merge
cd "$clone_dir"
git checkout "$branch1" --force
git merge --no-edit "$branch2"
retVal=$?

# report conflicts
if [ $retVal -ne 0 ]; then
    echo "Conflict"
fi

cd -

exit $retVal
