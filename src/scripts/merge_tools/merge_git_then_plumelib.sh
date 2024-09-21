#!/usr/bin/env sh

# usage: ./merge_git_then_plumelib.sh <clone_dir> <branch-1> <branch-2> <git_strategy> <plumelib_strategy>
# First runs `git merge`, then runs Plume-lib Merging to improve the result of `git merge`.
# <clone_dir> must contain a clone of a repository.
# Return code is 0 for merge success, 1 for merge failure, 2 for script failure.
# For merge failure, also outputs "Conflict" and aborts the merge.

set -o nounset

if [ "$#" -ne 5 ]; then
  echo "Usage: $0 CLONE_DIR BRANCH1 BRANCH2 GIT_STRATEGY PLUMELIB_STRATEGY" >&2
  exit 2
fi

clone_dir=$1
branch1=$2
branch2=$3
git_strategy=$4 #"-Xignore-space-change"
plumelib_strategy=$5 #"--only-adjacent"

## Perform merge

echo "$0: Merging $branch1 and $branch2 with git_strategy=$git_strategy and plumelib_strategy=$plumelib_strategy"

cd "$clone_dir" || { echo "$0: cannot cd to $clone_dir"; exit 2; }

git checkout "$branch1" --force
git config --local merge.conflictstyle diff3
git config --local mergetool.prompt false

# shellcheck disable=SC2086
git merge --no-edit $git_strategy "$branch2"

## Now, run Plume-lib Merging to improve the result of `git merge`.

git config --local merge.tool merge-plumelib
# shellcheck disable=SC2016
git config --local mergetool.merge-plumelib.cmd 'java-merge-tool.sh '"$plumelib_strategy"' ${BASE} ${LOCAL} ${REMOTE} ${MERGED}'
git config --local mergetool.merge-plumelib.trustExitCode true

case "$plumelib_strategy" in
    *"--no-imports"* | *"--only-adjacent"* | *"--only-annotations"* | *"--only-version-numbers"*)
        # The "imports" merger is not being used, so don't use the "--all" command-line option.
        all_arg=""
        ;;
    *)
        # The "imports" merger is being used, so use the "--all" command-line option.
        all_arg="--all"
        ;;
esac

git-mergetool.sh $all_arg --tool=merge-plumelib

# Check if there are still conflicts
diffs=$(git diff --name-only --diff-filter=U | sort)
if [ -z "$diffs" ]; then
    git add .
    git commit -m "Resolved conflicts by calling: git-mergetool.sh $all_arg --tool=merge-plumelib"
    exit 0
fi
echo "$0: diffs=$diffs"
echo "$0: Conflict after running in $(pwd):"
echo "  git merge --no-edit $git_strategy $branch2"
echo "  git-mergetool.sh $all_arg --tool=merge-plumelib"
exit 1
