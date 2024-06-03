# -*- coding: utf-8 -*-
"""Delete the keys containing 'imports' in the JSON files in the given directory."""

import os
import sys
import json
from pathlib import Path
from argparse import ArgumentParser


def count_import_keys(directory):
    """Count the number of keys containing 'imports' in the JSON files in the given directory."""
    count = 0
    for root, _, files in os.walk(directory):
        json_files = [f for f in files if f.endswith(".json")]
        for json_file in json_files:
            file_path = os.path.join(root, json_file)
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            # Count keys containing 'plumelib'
            keys_to_delete = [key for key in data if "plumelib" in key]
            count += len(keys_to_delete)
    return count


def delete_import_keys(directory):
    """Delete the keys containing 'imports' in the JSON files in the given directory."""
    total_deleted = 0
    for root, _, files in os.walk(directory):
        json_files = [f for f in files if f.endswith(".json")]
        for json_file in json_files:
            file_path = os.path.join(root, json_file)
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            # Record keys to delete
            keys_to_delete = [key for key in data.keys() if "plumelib" in key]
            if keys_to_delete:
                for key in keys_to_delete:
                    del data[key]
                    total_deleted += 1

            # Save the modified data back to file
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4)

    return total_deleted


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
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt."
    )
    args = parser.parse_args()
    cache_dir = Path(args.cache)
    potential_deletions = count_import_keys(cache_dir)
    if not cache_dir.exists():
        print(f"Directory '{cache_dir}' does not exist.")
        return

    if not args.yes:
        potential_deletions = count_import_keys(args.cache)
        print(f"Potential deletions: {potential_deletions}")
        confirm = input("Do you want to proceed with deleting these keys? (yes/no): ")
        if confirm.lower() != "yes":
            print("Operation cancelled.")
            sys.exit(0)

    total_deleted = delete_import_keys(args.cache)
    print(f"Total keys deleted: {total_deleted}")


if __name__ == "__main__":
    main()
