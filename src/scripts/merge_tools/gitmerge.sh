#!/usr/bin/env sh

# usage: ./gitmerge.sh <clone_dir> <branch-1> <branch-2> <git_strategy>
# Merges branch2 into branch1, in <clone_dir>, using merge strategy <git_strategy>.
# <clone_dir> must contain a clone of a repository.
# <git_strategy> is arguments to `git merge`, including -s and possibly -X.
# Return code is 0 for merge success, 1 for merge failure, 2 for script failure.
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

VERBOSE=
## Enable for debugging
# VERBOSE=YES


## Perform merge

cd "$clone_dir" || { echo "$0: cannot cd to $clone_dir"; exit 2; }

if [ -n "$VERBOSE" ] ; then
  echo "$0: about to run: git checkout $branch1 in $(pwd)"
fi
git checkout "$branch1" --force
if [ -n "$VERBOSE" ] ; then
  echo "$0: ran: git checkout $branch1 in $(pwd)"
fi
git config --local merge.conflictstyle diff3
git config --local mergetool.prompt false

echo "$0: about to run: git merge --no-edit $git_strategy $branch2 in $(pwd)"

# shellcheck disable=SC2086
git merge --no-edit $git_strategy "$branch2"
retVal=$?

if [ -n "$VERBOSE" ] ; then
  echo "$0: ran: git merge --no-edit $git_strategy $branch2 in $(pwd)"
fi

# report conflicts
if [ $retVal -ne 0 ]; then
    echo "gitmerge.sh: Conflict after running: git merge --no-edit $git_strategy $branch2"
fi

exit $retVal
