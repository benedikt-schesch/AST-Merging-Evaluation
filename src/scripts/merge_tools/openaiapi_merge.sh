#!/usr/bin/env bash
#
# Usage:
#   ./gitmerge-llm.sh <CLONE_DIR> <BRANCH1> <BRANCH2> <GIT_STRATEGY> <LLM_MODEL>
#
# This script checks out BRANCH1 in CLONE_DIR, then merges BRANCH2 into it
# using the provided git merge strategy (e.g. “-s recursive -X theirs”).
# If the merge produces conflicts, it calls the Python script resolve_conflicts.py
# on each conflicted file. The Python script uses an LLM (via Ollama) to
# attempt to resolve each conflict block.
#
# Exit codes:
#   0 - merge (and any LLM resolution) succeeded
#   1 - merge failed (conflicts left unresolved)
#   2 - script usage or internal failure

set -o nounset

if [ "$#" -ne 5 ]; then
  echo "Usage: $0 CLONE_DIR BRANCH1 BRANCH2 GIT_STRATEGY LLM_MODEL" >&2
  exit 2
fi

clone_dir=$1
branch1=$2
branch2=$3
git_strategy=$4
llm_model=$5
current_dir=$(pwd)

# VERBOSE=
# Uncomment the following line to enable debugging output:
VERBOSE=YES

# Change into the repository directory.
cd "$clone_dir" || { echo "$0: cannot cd to $clone_dir"; exit 2; }

if [ -n "$VERBOSE" ]; then
  echo "$0: Checking out branch $branch1 in $(pwd)"
fi
git checkout "$branch1" --force

# Configure Git to use diff3 style conflict markers.
git config --local merge.conflictstyle diff3
git config --local mergetool.prompt false

echo "$0: about to run: git merge --no-edit $git_strategy $branch2 in $(pwd)"
# shellcheck disable=SC2086
git merge --no-edit $git_strategy "$branch2"
merge_status=$?

if [ -n "$VERBOSE" ]; then
  echo "$0: git merge returned $merge_status"
fi

# If merge succeeded without conflict, we are done.
if [ $merge_status -eq 0 ]; then
  echo "Merge succeeded with no conflicts."
  exit 0
fi

echo "Merge encountered conflicts. Running LLM-based resolution using model '$llm_model'."

# Get list of files with merge conflicts.
conflict_files=$(git diff --name-only --diff-filter=U)
if [ -z "$conflict_files" ]; then
  echo "No conflict files detected, yet merge returned errors."
  exit 1
fi

# If any conflict file is a non java file, exit with 1.
if echo "$conflict_files" | grep -q -v '\.java$'; then
  echo "Non-Java conflict files detected. Manual intervention required."
  exit 1
fi

# cd to the directory where the script is located
cd "$current_dir" || { echo "$0: cannot cd to $current_dir"; exit 2; }

# Process each file with conflicts.
for file in $conflict_files; do
  file_path=$clone_dir/$file
  echo "Processing conflict file: $file_path"
  # Call the separate Python script to resolve conflicts in this file.
  python3 /scratch/scheschb/AST-Merging-Evaluation/src/scripts/merge_tools/resolve_conflicts_openaiapi.py "$file_path" "$llm_model"
  if [ $? -ne 0 ]; then
      echo "Conflict resolution did not resolve all conflicts in $file_path. Manual intervention required."
      exit 1
  fi
done

echo "LLM-based conflict resolution completed. Please review the changes and test thoroughly."
exit 0
