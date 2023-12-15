# -*- coding: utf-8 -*-
""" Delete all entries that finish with "intellimerge" in the
cache/sha_cache_entry directory and subdirectories.
"""

import json
from pathlib import Path


def delete_merge_tool_entries(delete: bool = False):
    """Delete all entries that finish with "intellimerge" in the
    cache/sha_cache_entry directory and subdirectories.
    """
    base_path = Path("cache/sha_cache_entry")
    n_deleted = 0
    # Iterate over all json files in the directory and subdirectories
    for json_file in base_path.glob("**/*.json"):
        # Load json file
        with json_file.open() as f:
            data = json.load(f)
        # Delete all entries that finish with "intellimerge"
        for key in list(data.keys()):
            if len(key) > 41 and "merge status" not in data[key]:
                n_deleted += 1
                if delete:
                    del data[key]
        # Save json file
        if delete:
            with json_file.open("w") as f:
                json.dump(data, f)
    return n_deleted


if __name__ == "__main__":
    deleted = delete_merge_tool_entries(delete=False)
    print("Total entries to be deleted: ", deleted)
    # Confirm deletion
    confirm = input("Confirm deletion? (y/n) ")
    if confirm == "y":
        deleted = delete_merge_tool_entries(delete=True)
    print(f"Deleted {deleted} entries.")
