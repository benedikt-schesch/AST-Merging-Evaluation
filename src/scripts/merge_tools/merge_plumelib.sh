#!/usr/bin/env sh

# usage: ./gitmerge_ort_imports_ignorespace.sh <clone_dir> <branch-1> <branch-2> <git_strategy> <merge_strategy>

clone_dir=$1
branch1=$2
branch2=$3
git_strategy=$4 #"-Xignore-space-change"
merge_strategy=$5 #"--only-adjacent"

echo "git_merge_plumelib: Merging $branch1 and $branch2 with git_strategy=$git_strategy and merge_strategy=$merge_strategy"

# shellcheck disable=SC2153 # "JAVA17_HOME is not a misspelling of "JAVA_HOME"
export JAVA_HOME="$JAVA17_HOME"

cd "$clone_dir" || exit 1

git checkout "$branch1" --force

git config --local merge.conflictstyle diff3
git config --local mergetool.prompt false
git config --local merge.tool merge-plumelib
# shellcheck disable=SC2016
git config --local mergetool.merge-plumelib.cmd 'java-merge-tool.sh '"$merge_strategy"' ${BASE} ${LOCAL} ${REMOTE} ${MERGED}'
git config --local mergetool.merge-plumelib.trustExitCode true

# shellcheck disable=SC2086
git merge --no-edit $git_strategy "$branch2"
retVal=$?

# report conflicts
yes | git mergetool --tool=merge-plumelib

# Check if there are still conflicts
diffs=$(git diff --name-only --diff-filter=U)
if [ -z "$diffs" ]; then
    git add .
    git commit -m "Resolved conflicts"
    exit 0
fi

echo "git_merge_plumelib: Conflicts still exist after running mergetool."
exit 1
