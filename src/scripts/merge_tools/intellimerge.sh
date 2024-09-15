#!/usr/bin/env sh

# usage: ./intellimerge.sh <clone_dir> <branch-1> <branch-2>
# <clone_dir> must contain a clone of a repository.
# Merges branch2 into branch1, in <clone_dir>.
# Return code is 0 for merge success, 1 for merge failure, 2 for script failure.
# For merge failure, also outputs "Conflict" and aborts the merge.

set -o nounset

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 CLONE_DIR BRANCH1 BRANCH2" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
ROOT_DIR="$(realpath "${SCRIPT_DIR}/../../../")"
intellimerge_relativepath=jars/IntelliMerge-1.0.9-all.jar
intellimerge_absolutepath="${ROOT_DIR}/${intellimerge_relativepath}"

clone_dir=$1
branch1=$2
branch2=$3
temp_out_dir="/tmp/intelli_temp_out_$$/"
temp_intellimerge_dir="/scratch/scheschb/intellimerge/intelli_temp_$$/"
mkdir $temp_out_dir

echo "IntelliMerge: $intellimerge_absolutepath"
echo "Clone dir: $clone_dir"
echo "Branch 1: $branch1"
echo "Branch 2: $branch2"
echo "Temp dir: $temp_out_dir"

clone_dir_absolutepath=$(realpath "$clone_dir")

# run intellimerge
cd "$clone_dir" || { echo "$0: cannot cd to $clone_dir" && exit 2; }

java -Djava.util.concurrent.ForkJoinPool.common.parallelism=1 -Djava.io.tmpdir="$temp_intellimerge_dir" -jar "$intellimerge_absolutepath" -r "$clone_dir_absolutepath" -b "$branch1" "$branch2" -o $temp_out_dir

# run git merge
git checkout "$branch1" --force

git merge --no-edit "$branch2"

# List conflicitng files
conflict_files=$(git diff --name-only --diff-filter=U)

# Initialize a flag to track conflict resolution
conflicts_resolved=true

# Iterate through conflicting files
for file in $conflict_files; do
    # Check if the conflicting file exists in the temp_out_dir
    if [ ! -f "$temp_out_dir$file" ]; then
        echo "Conflict not resolved for file: $file"
        conflicts_resolved=false
    fi
done

# If conflicts_resolved is false, there are unresolved conflicts
if [ "$conflicts_resolved" = false ]; then
    echo "Conflict detected. Aborting the merge. Please resolve the conflicts."
    echo "All conflicting files:"
    echo "$conflict_files"
    rm -rf $temp_out_dir $temp_intellimerge_dir
    exit 1
fi

# move files
find $temp_out_dir -type f | while read -r f; do
    # construct paths
    suffix=${f#"$temp_out_dir"}
    # CHeck that $f exists
    if [ ! -f "$f" ]; then
        echo "File $f does not exist. Skipping."
        continue
    fi
    echo "Moving $f to $clone_dir_absolutepath/$suffix"
    cp "$f" "$clone_dir_absolutepath/$suffix"
done
rm -rf $temp_out_dir $temp_intellimerge_dir

git add .
git commit -m "IntelliMerge: Merge $branch2 into $branch1"

rm -rf ours_refactorings.csv theirs_refactorings.csv

exit 0
