# -*- coding: utf-8 -*-
"""Delete the keys matching a given regex in the JSON files in the given directory."""

import os
import sys
import json
import re
from pathlib import Path
from argparse import ArgumentParser

def delete_keys_matching_regex(directory:Path, regex:str, dry_run:bool=False):
    """Delete the keys matching the given regex in the JSON files in the given directory."""
    total_deleted = 0
    pattern = re.compile(regex)
    for root, _, files in os.walk(directory):
        json_files = [f for f in files if f.endswith(".json")]
        for json_file in json_files:
            file_path = os.path.join(root, json_file)
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            # Record keys to delete
            keys_to_delete = [key for key in data.keys() if pattern.search(key)]
            if keys_to_delete:
                for key in keys_to_delete:
                    del data[key]
                    total_deleted += 1

            if not dry_run:
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
        "--regex",
        type=str,
        required=True,
        help="The regex to match keys for deletion.",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt."
    )
    args = parser.parse_args()
    cache_dir = Path(args.cache)
    regex = args.regex

    if not cache_dir.exists():
        print(f"Directory '{cache_dir}' does not exist.")
        return

    if not args.yes:
        potential_deletions = delete_keys_matching_regex(args.cache, regex, dry_run=True)
        print(f"Potential deletions: {potential_deletions}")
        confirm = input("Do you want to proceed with deleting these keys? (yes/no): ")
        if confirm.lower() != "yes":
            print("Operation cancelled.")
            sys.exit(0)

    total_deleted = delete_keys_matching_regex(args.cache, regex)
    print(f"Total keys deleted: {total_deleted}")


if __name__ == "__main__":
    main()
