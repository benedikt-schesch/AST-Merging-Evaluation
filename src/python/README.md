# Python Scripts for Merge Conflict Analysis




This directory contains Python scripts designed to facilitate the analysis of merge conflicts using various merge tools. The scripts allow users to recreate merges, analyze conflicts, and compare different merge algorithms' across the base, conflict, and programmer merge.




## Scripts Overview




- `diff3_analysis.py`: This script analyzes merge conflicts for two merge tools on a given conflict.

- It is different than the src/python/replay_merge, as it performs a 3 way diff between the base, conflicting branches, and the programmer merge.

- Outputs the differences between a pair of merge algorithms in a .txt file.




## Prerequisites




- Necessary Python packages installed inside conda or mamba environment(`pandas`, `GitPython`).



## Usage




### Analyzing a Single Merge Conflict




To analyze a conflicts comparing two merge tools inside src/python run:


python3 diff3_analysis.py <merge_tool1> <merge_tool2> <results_index> <output_directory>



Ex:

python3 diff3_analysis.py "gitmerge_ort" "spork" 32 "./mixed_results_spork"
