# ASTMerging

To delete all cached results:
  make clean-cache

# Requirements:

## Python

To install all the python requirements:
```
pip install -r requirements.txt
```

## Spork and Intellimerge

To download the Intellimerge and Spork jar:
```
wget https://github.com/Symbolk/IntelliMerge/releases/download/1.0.9/IntelliMerge-1.0.9-all.jar -P jars/
wget https://github.com/KTH/spork/releases/download/v0.5.0/spork-0.5.0.jar -O jars/spork.jar
```

### Alternative Python installation

If you don't want to mess with your local python installation you can create a python virtual environment to install all dependencies with the following commands:
```
pip3 install virtualenv
python3 -m venv venv
source venv/bin/activate
```
If you did the previous step make sure the virtual environemnt is activated when you use the repo (`source venv/bin/activate`)


## Ubuntu

```
sudo apt-get install -y jq
type -p curl >/dev/null || sudo apt install curl -y
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
&& sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
&& sudo apt update \
&& sudo apt install gh -y
curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | sudo bash
sudo apt-get install git-lfs
```

## MacOS

```
brew install jq
brew install gh
brew install git-lfs
```

# Run the code

## Test the stack
To test the stack, execute:
```
pytest
```
This will run the entire code on two small repos.
All the output data can be found in `small/`.
The final result is found in `small/result.csv`.
Directory `small/merges_small` contains all the merges.
Directory `small/merges_small_valid` contains all the merges and also stores if the parents of a merge pass tests.

## Perform full analysis

To run the stack on all repos:

```
./run_full.sh
```
This will run the entire code on all the repos.
All the output data can be found in `results/`.
The final result is found in `results/result.csv`.
Directory `results/merges` contains all the merges for each repo.
Directory `results/merges_valid` contains all the merges and also stores if the parents of a merge pass tests.

## Clean Cache

To clean the cache run `make clean-cache`.

## Style Checking

To run style checking run `make style`.

# Directory structure

 * run.sh -> This file executes each step of the stack.

 * run_small.sh -> This file executes the stack on two repositories.

 * run_full.sh -> This file executes the stack on all the repositories.

 * .workdir/ -> This folder is used for the local computations of each process.

 * .cache/ -> This folder is a cache for each computation. contains:

   * repos_result/ -> Caches the validation of each repository.

   * commit_test_result/ -> Caches the test results for a specific commit. Used for parent testing.

   * merge_test_results/ -> Caches the test results for specific merges. Used for merge testing.

 * repos/ -> In this folder each repo is cloned.

 * jars/ -> Location for the Intellimerge and Spork jars.

 * scratch/ -> If enabled each merge will be stored in this location.

 * results/ -> Stores the results for the full analysis.

 * small/ -> Stores the results for the small analysis.

 * data/ -> contains:

    * repos.csv -> List of all repos that fulfill the initial selection criterion.

    * repos_small.csv -> List of only 2 repos.

 * results/ -> contains:

    * valid_repos.csv -> Repos whose main branch passes its "test" buildfile target.

 * src/ -> contains the following scripts:

   * python/ -> contains the following scripts:

      * merge_tester.py -> Main file which performs merges and evaluates all the results across all projects.

      * validate_repos.py -> Checks out all repos and removes all repos that fail their tests on main branch.

      * latex_output.py -> Output latex code for the resulting plots and table.

      * test_parent_commits.py -> Tests if the parents of a commit pass their tests.

      * get_repos.py -> Downloads the repos list.

   * scripts/ -> contains the following scripts:
      * run_repo_tests.sh -> Runs a repo's programmer provided tests.

      * find_merge_commits.sh -> Finds all the merges in a project.
      
      * merge_tools/ -> contains the following scripts:
         * gitmerge.sh -> Executes git merge on a specific merge.
         * intellimerge.sh -> Executes intellimerge on a specific merge.
         * spork.sh -> Executes spork on a specific merge.
