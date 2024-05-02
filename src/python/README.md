# Python Scripts for Merge Conflict Analysis




This directory contains Python scripts designed to facilitate the analysis of merge conflicts using various merge tools. The scripts allow users to recreate merges, analyze conflicts, and compare different merge algorithms' effectiveness.




## Scripts Overview




- `diff3_analysis.py`: This script analyzes merge conflicts for two merge tools on a given conflict. The tool that failed to merge should come first as an argument.




## Prerequisites




- Python 3.x installed on your system.
- Necessary Python packages installed (e.g., `pandas`, `GitPython`).




## Usage




### Analyzing a Single Merge Conflict




To analyze a conflicts comparing two merge tools inside src/Python run:


python3 diff3_analysis.py <merge_tool1> <merge_tool2> <results_index> <output_directory>



Ex:

python3 diff3_analysis.py "gitmerge_ort" "spork" 32 "./mixed_results_spork"
