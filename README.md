# ASTMerging
Ensure all bash scripts have execute permissions

IMPORTANT: Use JDK 8
# Optional for the requirements
If you don't want to mess with your local python installation you can easily create a python virtual environment to install all dependencies with the following commands:
```
pip3 install virtualenv
python3 -m venv venv
source venv/bin/activate
```
If you did the previous step make sure the virtual environemnt is activated when you use the repo (`source venv/bin/activate`)
# Requirements:
To install all the python requirements:
```
pip install -r requirements.txt
```

To delete all cached results:
  make clean-cache

## Ubuntu

```
apt-get install -y jq
```

## MacOS

```
brew install jq
```

# Run the code

## Test the stack
To test the stack I recommend you execute:

```
./run_small.sh
```
This will run the entire code on two small repos.
All the output data can be found in small/
The final result is found in small/result.csv
small/merges_small contains all the merges
small/merges_small_valid contains all the merges and also stores if the parents of a merge pass tests.

## Perform full analysis

To run the stack on all repos:

```
./run.sh
```
This will run the entire code on all the repos.
All the output data can be found in results/
The final result is found in results/result.csv
results/merges contains all the merges for each repo
results/merges_valid contains all the merges and also stores if the parents of a merge pass tests.

# Structure


src/ -> contains the following scripts:

merge_tester.py -> Main file which performs merges and evaluates all the results across all projects

tester.sh -> Runs the tests in a specific repo

repos.csv -> List of all repos that fulfill the initial selection criterion  
repo_checker.py -> Checks out all repos and removes all repos that fail their tests on main branch

find_merge_commits.sh -> Finds all the merges in a project  
test_parent_commits.py -> Tests if the parents of a commit pass their tests

gitmerge.sh -> Executes git merge on a specific merge  
intellimerge.sh -> Executes intellimerge on a specific merge  
spork.sh -> Executes spork on a specific merge  

analyze.py -> Print the number of merges in each class (test failes, test passed, timeout...) for each tool (Intellimerge, Spork, Git)
plots.py -> Plotting script for the report


.workdir -> This folder is used by each process to make its computations.
