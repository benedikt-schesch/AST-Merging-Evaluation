# -*- coding: utf-8 -*-
"""Delete the keys containing 'imports' in the JSON files in the given directory."""

import os
import sys
import json
from pathlib import Path
from argparse import ArgumentParser


def traverse_cache_keys(directory, timing=False, delete=False, key="plumelib"):
    """Count the number of keys containing 'imports' in the JSON files in the given directory."""
    count = 0
    for root, _, files in os.walk(directory):
        json_files = [f for f in files if f.endswith(".json")]
        for json_file in json_files:
            if not timing and "merge_timing_results" in root:
                continue
            file_path = os.path.join(root, json_file)
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            keys_to_delete = [k for k in data if key in k]
            count += len(keys_to_delete)
            if delete:
                if keys_to_delete:
                    for k in keys_to_delete:
                        del data[k]

                # Save the modified data back to file
                with open(file_path, "w", encoding="utf-8") as file:
                    json.dump(data, file, indent=4)
    return count


def main():
    """Main function."""
    parser = ArgumentParser()
    parser.add_argument(
        "--cache",
        type=str,
        default="cache",
        help="The cache directory to delete keys from.",
    )
    parser.add_argument(
        "-timing",
        help="Delete the timing results as well.",
        action="store_true",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt."
    )
    args = parser.parse_args()
    cache_dir = Path(args.cache)
    if not cache_dir.exists():
        print(f"Directory '{cache_dir}' does not exist.")
        return

    if not args.yes:
        potential_deletions = traverse_cache_keys(args.cache, timing=args.timing)
        print(f"Potential deletions: {potential_deletions}")
        confirm = input("Do you want to proceed with deleting these keys? (yes/no): ")
        if confirm.lower() != "yes":
            print("Operation cancelled.")
            sys.exit(0)

    total_deleted = traverse_cache_keys(args.cache, timing=args.timing, delete=True)
    print(f"Total keys deleted: {total_deleted}")


if __name__ == "__main__":
    main()
