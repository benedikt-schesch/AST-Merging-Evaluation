# ASTMerging
Ensure all bash scripts have execute permissions

merge_tester.py -> Main file which performs merges and evaluates all the results across all projects

tester.sh -> Runs the tests in a specific repo

repos.csv -> List of all repos that fulfill the initial selection criterion  
repo_cloner.py -> Checks out all repos and removes all repos that fail their tests on main branch head  
valid_repos.csv -> All passing repos (output of repo_cloner)

find_merge_commits.sh -> Finds all the merges in a project  
test_parent_commits.py -> Tests if the parents of a commit pass their tests

gitmerge.sh -> Executes git merge on a specific merge  
intellimerge.sh -> Executes intellimerge on a specific merge  
spork.sh -> Executes spork on a specific merge  

result.csv -> Result of the analysis for each merge  
plots.py -> Plotting script for the report

jars/ -> tool downloads  
merges/ -> csv of scraped merges for each repo (merge, left, right, base)  
result/ -> repo pruning output  
sample-merges/ -> examples used to validate gitmerge.sh and spork.sh