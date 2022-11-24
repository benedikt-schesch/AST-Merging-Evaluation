#!/bin/bash

python3 src/python/repo_checker.py --repos_path data/repos_small.csv --output_path data/valid_repos_small.csv

sh src/scripts/find_merge_commits.sh data/valid_repos_small.csv merges_small

python3 src/python/test_parent_merges.py --repos_path data/valid_repos_small.csv --merges_path merges_small/ --output_dir merges_small_valid/

python3 src/python/merge_tester.py --repos_path data/valid_repos_small.csv --merges_path merges_small_valid/ --output_file data/result_small.csv