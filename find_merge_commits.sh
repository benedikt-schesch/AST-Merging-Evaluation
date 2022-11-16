#!/bin/bash

# This scripts find the merge commits from a given
# list of valid repositories
# Output the list of merge commit hashes, two parents 
# commit hashes, and base commit of the two parents

# Recieve list of repo names from valid_repos.csv
repos=( $(sed 1d valid_repos.csv | cut -d ',' -f3) )

# make merges directory if does not exists
rm -rf merges/
mkdir -p ./merges

# For each repo in list of repo names:
#   - clone the repo,
#   - cd into each repo
#   - find merge commit hashes in all branches
#   - for each merge commit:
#       - get parents commits
#       - get base commit of parents
#       - output (merge,parent1,parent2,  ) "/merges/[repo_name].csv"
for repo in ${repos[@]} 
do
  repo_name="$(cut -d '/' -f2 <<< "$repo")"
  rm -rf ./$repo_name

  git clone https://github.com/$repo.git
  cd $repo_name
  merge_commits=$(git log --merges --pretty=format:"%H")
  for merge_commit in ${merge_commits[@]}
  do
    merge_parents_commits=( $(git log --pretty=%P -n 1 $merge_commit) )
    merge_base_commit=$(git merge-base ${merge_parents_commits[0]} ${merge_parents_commits[1]})
    echo "$merge_commit,${merge_parents_commits[0]},${merge_parents_commits[1]},$merge_base_commit" >> ../merges/$repo_name.csv
  done
  cd ..
  rm -rf $repo_name/
done