# -*- coding: utf-8 -*-
"""Delete the keys containing 'imports' in the JSON files in the given directory."""

import os
import json


def count_import_keys(directory):
    """Count the number of keys containing 'imports' in the JSON files in the given directory."""
    count = 0
    for root, _, files in os.walk(directory):
        json_files = [f for f in files if f.endswith(".json")]
        for json_file in json_files:
            file_path = os.path.join(root, json_file)
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            # Count keys containing 'imports'
            keys_to_delete = [key for key in data if "imports" in key]
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
            keys_to_delete = [key for key in data.keys() if "imports" in key]
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
    directory = "cache/merge_timing_results"
    potential_deletions = count_import_keys(directory)
    print(f"Potential deletions: {potential_deletions}")
    confirm = input("Do you want to proceed with deleting these keys? (yes/no): ")
    if confirm.lower() == "yes":
        total_deleted = delete_import_keys(directory)
        print(f"Total keys deleted: {total_deleted}")
    else:
        print("Operation cancelled.")


if __name__ == "__main__":
    main()
