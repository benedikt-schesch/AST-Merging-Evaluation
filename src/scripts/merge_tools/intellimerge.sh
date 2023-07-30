#!/usr/bin/env sh

# usage: ./intellimerge.sh <clone_dir> <branch-1> <branch-2>
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

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
ROOT_DIR="$(realpath "${SCRIPT_DIR}/../../../")"
intellimerge_relativepath=jars/IntelliMerge-1.0.9-all.jar
intellimerge_absolutepath="${ROOT_DIR}/${intellimerge_relativepath}"

clone_dir=$1
branch1=$2
branch2=$3
temp_dir=".workdir/intelli_temp_$$/"
mkdir $temp_dir

# run intellimerge
java -jar "$intellimerge_absolutepath" -r "$clone_dir" -b "$branch1" "$branch2" -o $temp_dir

# run git merge
cd "$clone_dir"
git checkout "$branch1" --force
# collect initial counts of strings that are conflict markers, but appear in the clone.
m1a=$(grep -ro '^<<<<<<<$' . | wc -l)
m2a=$(grep -ro '^=======$' . | wc -l)
m3a=$(grep -ro 'n^>>>>>>>$' . | wc -l)
git merge --no-edit "$branch2"
cd -

# move files
find $temp_dir -type f | while read -r f; do
    # construct paths
    suffix=${f#"$temp_dir"}
    mv "$f" "$clone_dir/$suffix"
done
rm -rf $temp_dir

# report conflicts
m1b=$(grep -ro '^<<<<<<<$' "$clone_dir" | wc -l)
m2b=$(grep -ro '^=======$' "$clone_dir" | wc -l)
m3b=$(grep -ro '^>>>>>>>$' "$clone_dir" | wc -l)
if [ "$m1a" -ne "$m1b" ] && [ "$m2a" -ne "$m2b" ] && [ "$m3a" -ne "$m3b" ]; then
    echo "Conflict"
    exit 1
fi
exit 0
