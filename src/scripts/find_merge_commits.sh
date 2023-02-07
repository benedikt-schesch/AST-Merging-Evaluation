#!/bin/bash

# usage: ./find_merge_commits.sh <repo-list> <output-dir>

# This script finds the merge commits from a given
# list of valid repositories.
# Merge commits maybe be of mainline branch, feature branches, 
# and pull requests (both opened and closed).
# Output a list of branch name, merge commit hashes, two parents 
# commit hashes, and base commit of the two parents inside of <output-dir>

set -e 
set -o nounset

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 REPO_LIST OUTPUT_DIR" >&2
  exit 1
fi

# Receive list of repo names from list of valid repos (arg #1)
VALID_REPOS=$(sed 1d $1 | cut -d ',' -f3)

# Get the commits of a repo's (arg #1) pull request (arg #2)
GET_COMMITS_FROM_PR() {
    gh api \
        -H "Accept: application/vnd.github+json" \
        --method GET \
        --paginate \
        "/repos/$1/pulls/$2/commits"
}


if [ ! -d "$2" ]; then
    mkdir "$2"
fi

for REPO in "${VALID_REPOS[@]}"
do
    # Getting merge commits of mainline and feature branches
    # For each repo in list of repo names:
    #   - clone the repo,
    #   - cd into each repo
    #   - get all branches name
    #   - for each branch:
    #       - checkout branch
    #       - for each merge commit:
    #           - get parents commits
    #           - get base commit of parents
    #           - output (branch_name,merge,parent1,parent2,base)"

    REPO_NAME=$(cut -d '/' -f2 <<< "$REPO")
    rm -rf "./$REPO_NAME"
    
    # Skip repos that have already been analyzed
    FILE=$2/$REPO_NAME.csv
    echo "$FILE"
    if test -f "$FILE"; then
        continue
    fi
    
    # Header for $REPO_NAME.csv
    echo "branch_name,merge_commit,parent_1,parent_2,base_commit" \
        > "$2/$REPO_NAME.csv"

    git clone "https://github.com/$REPO.git"
    cd "$REPO_NAME"

    # Get all branches name
    BRANCHES=$(git branch -a --format="%(refname:lstrip=3)" \
                | grep -vE '^[[:space:]]*$|HEAD' | sort -u)
    
    # Feature branches often diverge from mainline branch (master)
    # and carry redundant merge commit tuple (merge,parents,base) 
    # contained in mainline branch
    # We want to eliminate redundant merge commit tuple, 
    # so we will retrieve merge commit tuple of mainline 
    # branch first, then go through other feature branchs 
    # and only retrieve new merge commit tuple.
    # Get merge commits
    
    DEFAULT_BRANCH=$(git branch --show-current)
    {
        MERGE_COMMITS="$(git log --merges --pretty=format:"%H")"
        for MERGE_COMMIT in "${MERGE_COMMITS[@]}"
        do
            MERGE_PARENTS=( $(git log --pretty=%P -n 1 "$MERGE_COMMIT") )
            MERGE_BASE=$(git merge-base \
                        "${MERGE_PARENTS[0]}" "${MERGE_PARENTS[1]}")
            
            echo "$DEFAULT_BRANCH,$MERGE_COMMIT,${MERGE_PARENTS[0]},${MERGE_PARENTS[1]},$MERGE_BASE" >> "../$2/$REPO_NAME.csv"
        done
    }

    for BRANCH in "${BRANCHES[@]}"
    do
        # ignore master branch, commits already retrieved
        if [[ "$BRANCH" != "$DEFAULT_BRANCH" ]]
        then
            git checkout -B "$BRANCH" "origin/$BRANCH"

            # Get merge commits
            MERGE_COMMITS=$(git log --merges --pretty=format:"%H")
            for MERGE_COMMIT in "${MERGE_COMMITS[@]}"
            do
                MERGE_PARENTS=( $(git log --pretty=%P -n 1 "$MERGE_COMMIT") )
                MERGE_BASE=$(git merge-base \
                            "${MERGE_PARENTS[0]}" "${MERGE_PARENTS[1]}")
                COMMIT_TUPLE="$MERGE_COMMIT,${MERGE_PARENTS[0]},${MERGE_PARENTS[1]},$MERGE_BASE"
                
                # add commit tuple if not seen before
                if ! grep --quiet "$COMMIT_TUPLE" "../$2/$REPO_NAME.csv"
                then
                    echo "$BRANCH,$MERGE_COMMIT,${MERGE_PARENTS[0]},${MERGE_PARENTS[1]},$MERGE_BASE" >> "../$2/$REPO_NAME.csv"
                fi
            done
        fi
    done

    # Getting merges from pull requests (including closed PRs)
    # Get list of all PRs
    # For each PR (identified by PR number):
    #   - grab list of commits in PR
    #   - for each commit in PR:
    #       - get commit sha
    #       - check if there exists two parent commits
    #           - get parents commits
    #           - checkout PR as branch
    #           - get base commits of parents
    #           - output (branch_name,merge,parent1,parent2,base)"

    # Get list of all PRs (number)
    PULL_REQUESTS=$(gh api \
                    -H "Accept: application/vnd.github+json" \
                    --method GET \
                    --paginate \
                    --jq '.[].number' \
                    "/repos/$REPO/pulls" \
                    -f state=all)
    
    for PR_NUMBER in "${PULL_REQUESTS[@]}"
    do
        COMMITS=( $(GET_COMMITS_FROM_PR "$REPO" "$PR"_NUMBER | jq -r '.[].sha') )
        for (( i=0; i < ${#COMMITS[@]}; i++ ))
        do
            PARENTS_RESULT=( $(GET_COMMITS_FROM_PR "$REPO" "$PR_NUMBER" \
                            | jq --arg i "$i" '.[($i | tonumber)].parents') )
            NUM_OF_PARENTS=$(GET_COMMITS_FROM_PR "$REPO" "$PR_NUMBER" \
                            | jq --arg i "$i" '.[($i | tonumber)].parents | length')
            
            # A merge commit is found if it has two parents,
            # ignore non-merge commits
            if [[ $NUM_OF_PARENTS -eq 2 ]]
            then
                MERGE_COMMIT=${COMMITS[$i]}
                MERGE_PARENTS=( $(GET_COMMITS_FROM_PR "$REPO" "$PR_NUMBER" \
                                | jq -r --arg i "$i" '.[($i | tonumber)].parents[].sha') )
                
                # Create a new local branch from PR_NUMBER in order to reference commits on PR
                git fetch origin "pull/$PR_NUMBER/head:$PR_NUMBER"
                git checkout -B "$PR_NUMBER"
                
                MERGE_BASE=$(git merge-base "${MERGE_PARENTS[0]}" "${MERGE_PARENTS[1]}")
                echo "$PR_NUMBER,$MERGE_COMMIT,${MERGE_PARENTS[0]},${MERGE_PARENTS[1]},$MERGE_BASE" >> "../$2/$REPO_NAME.csv"
            fi
        done
    done
    
    cd ..
    rm -rf "$REPO_NAME"
done
