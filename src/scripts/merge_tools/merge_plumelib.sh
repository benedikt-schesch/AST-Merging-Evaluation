#!/usr/bin/env sh

# usage: ./gitmerge_ort_imports_ignorespace.sh <clone_dir> <branch-1> <branch-2> <git_strategy> <merge_strategy>

clone_dir=$1
branch1=$2
branch2=$3
git_strategy=$4 #"-Xignore-space-change"
merge_strategy=$5 #"--only-adjacent"

echo "$0: Merging $branch1 and $branch2 with git_strategy=$git_strategy and merge_strategy=$merge_strategy"
echo "HEAD = $(git rev-parse HEAD)"
git branch --list -a -v --no-color
echo "----"
git show-branch
echo "----"
git show-ref
echo "----"
git tag --list --color=never
echo "----"
git fetch --dry-run
echo "----"

cd "$clone_dir" || (echo "$0: cannot cd to $clone_dir" ; exit 1)

git checkout "$branch1" --force
echo "$branch1 = $(git rev-list -n 1 "$branch1")"

git config --local merge.conflictstyle diff3
git config --local mergetool.prompt false
git config --local merge.tool merge-plumelib
# shellcheck disable=SC2016
git config --local mergetool.merge-plumelib.cmd 'java-merge-tool.sh '"$merge_strategy"' ${BASE} ${LOCAL} ${REMOTE} ${MERGED}'
git config --local mergetool.merge-plumelib.trustExitCode true

# shellcheck disable=SC2086
git merge --no-edit $git_strategy "$branch2"

case "$merge_strategy" in
    *"--no-java-imports"* | *"--only-adjacent"* | *"--only-java-annotations"* | *"--only-version-numbers"*)
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
diffs=$(git diff --name-only --diff-filter=U)
if [ -z "$diffs" ]; then
    git add .
    git commit -m "merge_plumelib.sh: Resolved conflicts by calling: git-mergetool.sh $all_arg --tool=merge-plumelib"
    exit 0
fi
echo "$0: diffs=$diffs"
echo "$0: Conflict after running in $(pwd):"
echo "  git merge --no-edit $git_strategy $branch2"
echo "  git-mergetool.sh $all_arg --tool=merge-plumelib"
exit 1
