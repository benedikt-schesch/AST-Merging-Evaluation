#!/usr/bin/env sh

# usage: ./gitmerge.sh <clone_dir> <branch-1> <branch-2> <strategy> [no-git-merge-abort]
# <clone_dir> must contain a clone of a repository.
# <strategy> is arguments to `git merge`, including -s and possibly -X.
# Merges branch2 into branch1, in <clone_dir>, using merge strategy <strategy>.
# For merge success, return code is 0.
# For merge failure:
#  * return code is 1.
#  * outputs "Conflict".
#  * aborts the merge, unless a 5th command-line argument is provided.

set -o nounset

if [ "$#" -ne 4 ] && [ "$#" -ne 5 ]; then
  echo "Usage: $0 CLONE_DIR BRANCH1 BRANCH2 STRATEGY [no-git-merge-abort]" >&2
  exit 1
fi

clone_dir=$1
branch1=$2
branch2=$3
strategy=$4
# If this variable is non-empty, don't run `git merge --abort`.
no_git_merge_abort=$5

# perform merge
cd "$clone_dir" || exit 1
git checkout "$branch1" --force
echo "Running: git merge --no-edit $strategy $branch2"
# shellcheck disable=SC2086
git merge --no-edit $strategy "$branch2"
retVal=$?

# report conflicts
if [ $retVal -ne 0 ]; then
    echo "Conflict"
    if [ -z "$no_git_merge_abort" ] ; then
        git merge --abort
    fi
fi

exit $retVal
