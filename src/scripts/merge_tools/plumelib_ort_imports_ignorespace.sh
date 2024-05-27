#!/usr/bin/env sh

# usage: ./gitmerge_ort_imports_ignorespace.sh <clone_dir> <branch-1> <branch-2>

MERGE_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"
clone_dir=$1
branch1=$2
branch2=$3
git_strategy="-s ort -Xignore-space-change"
plumelib_strategy="--only-imports"
"$MERGE_SCRIPTS_DIR"/gitmerge.sh "$clone_dir" "$branch1" "$branch2" "$strategy" "$plumelib_strategy"