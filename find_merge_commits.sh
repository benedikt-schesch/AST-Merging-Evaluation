#!/bin/bash

# This scripts find the merge commits from a given list of valid repositories
# Output the list of merge commit hashes, as well the two parents commit hashes

# Recieve list of repo names from valid_repos.csv
repos=( $(sed 1d valid_repos.csv | cut -d ',' -f3) )

# make merges directory if does not exists
mkdir -p ./merges

# For each repo in list of repo names:
#   - clone the repo,
#   - cd into each repo
#   - find merge commits (merge, parents) hashes in all branches
#       - git log --merges --prety=format:"%H, %P"
#       - output: save into "[repo_name]_merge_commits.csv"
for repo in ${repos[@]} 
do
  git clone https://github.com/$repo.git
  repo_name="$(cut -d '/' -f2 <<< "$repo")"
  cd $repo_name
  git log --merges --pretty=format:"%H, %P" > ../merges/$repo_name.csv
  cd ..
  rm -rf $repo_name/
done


