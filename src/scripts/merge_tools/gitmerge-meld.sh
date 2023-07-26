#!/usr/bin/env sh

# usage: ./gitmerge-meld.sh <clone_dir> <branch-1> <branch-2>

MERGE_DIR="$(dirname "$0")"
clone_dir=$1
branch1=$2
branch2=$3
git config mergetool.meld.useAutoMerge True
"$MERGE_DIR"/gitmerge-ort.sh "$clone_dir" "$branch1" "$branch2"
retVal=$?

cd "$clone_dir"
git mergetool --tool=meld

# report conflicts
if [ $retVal -ne 0 ]; then
    echo "Conflict"
    git merge --abort
fi

cd -

exit $retVal
