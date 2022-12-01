#!/bin/bash

python3 src/python/repo_checker.py --repos_path data/repos.csv --output_path data/valid_repos.csv

sh src/scripts/find_merge_commits.sh data/valid_repos.csv merges

python3 src/python/reduce_merges.py --merges_path merges/ --output_dir merges_subsampled/ --max_merges 100

python3 src/python/test_parent_merges.py --repos_path data/valid_repos.csv --merges_path merges_subsampled/ --output_dir merges_valid/

python3 src/python/merge_tester.py --repos_path data/valid_repos.csv --merges_path merges_valid/ --output_file data/result.csv