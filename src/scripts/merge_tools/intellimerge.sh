#!/usr/bin/env sh

# usage: ./intellimerge.sh <clone_dir> <branch-1> <branch-2>
# <clone_dir> must contain a clone of a repository.
# Merges branch2 into branch1, in <clone_dir>.
# Return code is 0 for merge success, 1 for merge failure.
# For merge failure, also outputs "Conflict" and aborts the merge.

set -o nounset

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 CLONE_DIR BRANCH1 BRANCH2" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
ROOT_DIR="$(realpath "${SCRIPT_DIR}/../../../")"
intellimerge_relativepath=jars/IntelliMerge-1.0.9-all.jar
intellimerge_absolutepath="${ROOT_DIR}/${intellimerge_relativepath}"

clone_dir=$1
branch1=$2
branch2=$3
temp_dir="/tmp/intelli_temp_$$/"
mkdir $temp_dir

echo "IntelliMerge: $intellimerge_absolutepath"
echo "Clone dir: $clone_dir"
echo "Branch 1: $branch1"
echo "Branch 2: $branch2"
echo "Temp dir: $temp_dir"

# run intellimerge
java -jar "$intellimerge_absolutepath" -r "$clone_dir" -b "$branch1" "$branch2" -o $temp_dir

# run git merge
cd "$clone_dir" || exit 1
git checkout "$branch1" --force

git merge --no-edit "$branch2"
cd - || exit 1

# move files
find $temp_dir -type f | while read -r f; do
    # construct paths
    suffix=${f#"$temp_dir"}
    mv "$f" "$clone_dir/$suffix"
done
rm -rf $temp_dir

cd "$clone_dir" || exit 1
# Detect conflicts using Git commands
conflict_files=$(git diff --name-only --diff-filter=U)

if [ -n "$conflict_files" ]; then
    echo "Conflict detected in the following files:"
    echo "$conflict_files"
    exit 1
fi

echo "No conflicts detected. $conflict_files"
exit 0
