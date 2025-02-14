#!/bin/bash
# trim_csvs.sh: Trim all CSV files in results/combined/merges (recursively)
#              to the first n lines, where n is provided as a parameter.

# Check that exactly one argument is provided.
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 n"
    echo "  n: Number of lines to keep in each CSV file."
    exit 1
fi

# Check that the parameter is a positive integer.
if ! [[ "$1" =~ ^[0-9]+$ ]] || [ "$1" -eq 0 ]; then
    echo "Error: n must be a positive integer."
    exit 1
fi

n="$1"
# Create folder of format results/combined_n
cp -r results/combined "results/combined_trimed_$n/"
base_dir="results/combined_trimed_$n/merges"

# Use find to locate all .csv files (recursively) and process each one.
find "$base_dir" -type f -name "*.csv" -print0 | while IFS= read -r -d '' file; do
    echo "Trimming file: $file"
    # Create a temporary file, write the first n lines, then overwrite the original file.
    tmpfile=$(mktemp) || { echo "Failed to create temporary file"; exit 1; }
    head -n "$n" "$file" > "$tmpfile" && mv "$tmpfile" "$file"
done

echo "Trimming complete."
