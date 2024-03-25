# Python Scripts for Merge Conflict Analysis


This directory contains Python scripts designed to facilitate the analysis of merge conflicts using various merge tools. The scripts allow users to recreate merges, analyze conflicts, and compare different merge algorithms' effectiveness.


## Scripts Overview


- `diff3_analysis.py`: This script analyzes merge conflicts for a single specified merge tool and commit.
- `run_diff3_analysis.py`: This script automates the analysis across multiple commits and merge tools, aggregating the results.


## Prerequisites


- Python 3.x installed on your system.
- Necessary Python packages installed (e.g., `pandas`, `GitPython`).


## Usage


### Analyzing a Single Merge Conflict


To analyze merge conflicts using a specific merge tool for a single commit:

python3 diff3_analysis.py <merge_tool> <results_index> <output_directory>


Ex:

python3 diff3_analysis.py gitmerge_ort 582 ./merge_conflict_analysis_diffs/582/gitmerge_ort


<merge_tool>: The merge tool to use for the analysis (e.g., gitmerge_ort).
<results_index>: The index of the commit in the dataset.
<output_directory>: The directory where the analysis results will be saved.


Running Bulk Analysis
To run the analysis over multiple commits and all merge tools:

python3 run_diff3_analysis.py --results_index <indexes> --repo_output_dir "<output_directory>"


Ex:

python3 run_diff3_analysis.py --results_index 582,427,930 --repo_output_dir "./merge_conflict_analysis_diffs"

<indexes>: Comma-separated list of commit indices to analyze. Example: 582,427,930.
<output_directory>: The directory where the bulk analysis results will be saved.
