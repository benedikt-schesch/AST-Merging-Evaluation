# Evaluation of VCS merging algorithms

![small-test](https://github.com/benedikt-schesch/AST-Merging-Evaluation/actions/workflows/small-test.yml/badge.svg)

![check-style](https://github.com/benedikt-schesch/AST-Merging-Evaluation/actions/workflows/check-style.yml/badge.svg)

## Requirements

### Python

To install all the python requirements:

```bash
pip install -r requirements.txt
```

### Alternative Python installation

If you don't want to mess with your local python installation you can create a python virtual environment to install all dependencies with the following commands:

```bash
pip3 install virtualenv
python3 -m venv venv
source venv/bin/activate
```

If you did the previous step make sure the virtual environemnt is activated when you use the repo (`source venv/bin/activate`).

### Maven

Make sure you use maven version 3.9.*.

### Ubuntu

```bash
sudo apt-get install -y jq
command -v curl >/dev/null || sudo apt install curl -y
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
&& sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
&& sudo apt update \
&& sudo apt install gh -y
curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | sudo bash
```

### MacOS

```bash
brew install jq
brew install gh
```

### Java

Make sure you install Java 8, 11 and 17. You need to set the `JAVA8_HOME`, `JAVA11_HOME` and `JAVA17_HOME` environment variables to the respective Java installations.

---

## Run the code

### Test the stack

To test the stack, execute:

```bash
make small-test
```

This runs the entire code on two small repos.
The output data appears in `results-small/`.
 * `results-small/result.csv`: the final result
 * `results-small/merges_small/` contains all the merges.
 * `results-small/merges_small_valid/` contains all the merges and also records whether the parents of a merge pass tests.

### Perform full analysis

To run the stack on all repos:

```bash
./run_full.sh
```

To run the stack on all repos and also diff the merges outputs:

```bash
./run_full.sh -d
```

This will run the entire code on all the repos and automatically decompress the cache if `cache/` does not exist.
All the output data can be found in `results/`.
The final result is found in `results/result.csv`.
Directory `results/merges` contains all the merges for each repo.
Directory `results/merges_valid` contains all the merges and also stores if the parents of a merge pass tests.

To delete cache entries on failed merges, inconsistent merges, failed trivial merges and reexecute the stack multiple times over and over:

```bash
./run_full_restart.sh <n_repeat>
```

To execute `run_full.sh` on multiple machines in parallel create a machine address list in `machines.txt` and run:

```bash
./run_multiple_machine.sh main machines.txt <project_path_on_machine>
```

### Load the stored cache

To decompress the cache run `make decompress-cache`. This is done automatically in `run_full.sh` if `cache/` does not exist.

### Store the cache

To store the cache `make compress-cache`.

### Clean Cache

To clean the cache run `make clean-cache`.

### Clean Workspace

To cleanup the workspace:`make clean`

### Style Checking

To run style checking run `make style`.

---

## Directory structure

### Commited files

* run.sh -> This file executes each step of the stack.

* run_small.sh -> This file executes the stack on two repositories.

* run_full.sh -> This file executes the stack on all the repositories.

* run_full_restart.sh -> This file executes the stack and repeats failed merges, inconsistent merges and failed trivial multiple times.

* src/ -> contains the following scripts:

  * python/ -> contains the following scripts:

    * merge_tester.py -> Main file which performs merges and evaluates all the results across all projects.

    * validate_repos.py -> Checks out all repos and removes all repos that fail their tests on main branch.

    * latex_output.py -> Output latex code for the resulting plots and table.

    * test_parent_commits.py -> Tests if the parents of a commit pass their tests.

    * get_repos.py -> Downloads the repos list.

    * cache_merger.py -> Merges the current cache with the cache.tar

    * delete_cache_entries.py -> Delete specific cache entries.

    * delete_inconsistent_merge_results.py -> Delete inconsistent merge results.

    * delete_failed_trivial_merge_results.py -> Delete failed trivial merge results.

  * scripts/ -> contains the following scripts:

    * run_repo_tests.sh -> Runs a repo's programmer provided tests.

    * merge_tools/ -> contains the following scripts:
      * gitmerge.sh -> Executes git merge on a specific merge.
      * intellimerge.sh -> Executes intellimerge on a specific merge.
      * spork.sh -> Executes spork on a specific merge.

    * utils/
      * run_remotely.sh -> Runs the full stack on a remote machine.
      * run_multiple_machine.sh -> Runs the full stack on multiple remote machines.

  * src/main/java/astmergeevaluation/FindMergeCommits.java -> Finds all merge commits in a repo.

* input_data/ -> Input data, which is a list of repositories; see its README.md.

### Uncommited Files

* cache/ -> This folder is a cache for each computation. contains:

  * test_result/ -> Caches the test results for a specific commit. Used for parent testing and repo validation.

  * merge_test_results/ -> Caches the test results for specific merges. Used for merge testing. First line indicates the merge result, second line indicates the runtime.

  * merge_diff_results/ -> Caches the diff results for specific merges.

* test_cache/ -> This folder is a cache for each test computation. contains:

  * test_result/ -> Caches the test results for a specific commit. Used for parent testing and repo validation.

  * merge_test_results/ -> Caches the test results for specific merges. Used for merge testing. First line indicates the merge result, second line indicates the runtime.

* .workdir/ -> This folder is used for the local computations of each process and contaent is named by Unix process (using "$$").

* repos/ -> In this folder each repo is cloned.

* results/ -> Contains all the results for the full analysis.

* results-small/ -> Contains all the results for the small analysis.

* jars/ -> Location for the Intellimerge and Spork jars.

* scratch/ -> If STORE_SCRATCH is enabled in `merge_tester.py`, each merge will be stored in this location.
