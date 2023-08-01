#!/usr/bin/env sh

# usage: ./git-hires-merge.sh <clone_dir> <branch-1> <branch-2>

clone_dir=$1
branch1=$2
branch2=$3

cd "$clone_dir" || exit 1

git checkout "$branch1" --force

export GIT_HIRES_MERGE_NON_INTERACTIVE_MODE=True
attributes_file=".git/info/attributes"
echo "* merge=git-hires-merge" >> "$attributes_file"


git merge --no-edit "$branch2" 
retVal=$?

# report conflicts
if [ "$retVal" -ne 0 ]; then
    echo "Conflict"
    git merge --abort
fi

exit "$retVal"
