#!/bin/bash

python3 src/python/repo_checker.py --repos_path data/repos.csv --output_path results/valid_repos.csv --num_cpu $1

sh src/scripts/find_merge_commits.sh results/valid_repos.csv results/merges

python3 src/python/reduce_merges.py --merges_path results/merges/ --output_dir results/merges_subsampled/ --max_merges 100

python3 src/python/test_parent_merges.py --repos_path results/valid_repos.csv --merges_path results/merges_subsampled/ --output_dir results/merges_valid/ --num_cpu $1

python3 src/python/merge_tester.py --repos_path results/valid_repos.csv --merges_path results/merges_valid/ --output_file results/result.csv --num_cpu $1