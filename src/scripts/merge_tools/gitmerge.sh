#!/usr/bin/env sh

# usage: ./gitmerge.sh <clone_dir> <branch-1> <branch-2> <git_strategy>
# <clone_dir> must contain a clone of a repository.
# <git_strategy> is arguments to `git merge`, including -s and possibly -X.
# Merges branch2 into branch1, in <clone_dir>, using merge strategy <git_strategy>.
# Return code is 0 for merge success, 1 for merge failure.
# For merge failure, also outputs "Conflict" and aborts the merge.

set -o nounset

if [ "$#" -ne 4 ]; then
  echo "Usage: $0 CLONE_DIR BRANCH1 BRANCH2 GIT_STRATEGY" >&2
  exit 2
fi

clone_dir=$1
branch1=$2
branch2=$3
git_strategy=$4

## Perform merge

cd "$clone_dir" || (echo "$0: cannot cd to $clone_dir" ; exit 2)

git checkout "$branch1" --force
git config merge.conflictstyle zdiff3

echo "Running: git merge --no-edit $git_strategy $branch2"
# shellcheck disable=SC2086
git merge --no-edit $git_strategy "$branch2"
retVal=$?

# report conflicts
if [ $retVal -ne 0 ]; then
    echo "gitmerge.sh: Conflict after running: git merge --no-edit $git_strategy $branch2"
fi

exit $retVal
