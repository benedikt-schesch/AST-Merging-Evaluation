#!/usr/bin/env sh

# usage: <scriptname> <clone_dir> <branch-1> <branch-2>

set -o nounset

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 CLONE_DIR BRANCH1 BRANCH2" >&2
  exit 1
fi

clone_dir=$1
branch1=$2
branch2=$3

SCRIPTDIR="$(cd "$(dirname "$0")" && pwd -P)"

# Print the current PATH
echo "$0 PATH: $PATH"

cd "$clone_dir" || { echo "$0: cannot cd to $clone_dir from $(pwd)"; exit 2; }

git checkout "$branch1" --force

export GIT_HIRES_MERGE_NON_INTERACTIVE_MODE=True
attributes_file=".git/info/attributes"
echo "* merge=git-hires-merge" >> "$attributes_file"

git config --local merge.git-hires-merge.name "An interactive merge driver for resolving conflicts on individual or adjacent lines"
git config --local merge.git-hires-merge.driver "${SCRIPTDIR}/git-hires-merge %O %A %B %L %P"
git config --local merge.git-hires-merge.recursive "binary"
git config --local merge.conflictstyle diff3

git merge --no-edit "$branch2"
retVal=$?

# report conflicts
if [ "$retVal" -ne 0 ]; then
    echo "git_hires_merge: Conflict"
fi

exit "$retVal"
