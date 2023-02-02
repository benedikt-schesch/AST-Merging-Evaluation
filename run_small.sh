#!/bin/bash

python3 src/python/repo_checker.py --repos_path data/repos_small.csv --output_path small/valid_repos.csv  --num_cpu $1

sh src/scripts/find_merge_commits.sh small/valid_repos.csv small/merges_small

python3 src/python/test_parent_merges.py --repos_path small/valid_repos.csv --merges_path small/merges_small/ --output_dir small/merges_small_valid/ --num_cpu $1

python3 src/python/reduce_merges.py --merges_path small/merges_small_valid/ --output_dir small/merges_small_valid_subsamples/ --max_merges 10

python3 src/python/merge_tester.py --repos_path small/valid_repos.csv --merges_path small/merges_small_valid_subsamples/ --output_file small/result.csv  --num_cpu $1