# -*- coding: utf-8 -*-
""" Delete all entries that finish with "intellimerge" in the
cache/sha_cache_entry directory and subdirectories.
"""

import json
from pathlib import Path

base_path = Path("cache/sha_cache_entry")
deleted = 0
# Iterate over all json files in the directory and subdirectories
for json_file in base_path.glob("**/*.json"):
    # Load json file
    with json_file.open() as f:
        data = json.load(f)
    # Delete all entries that finish with "intellimerge"
    for key in list(data.keys()):
        if len(key) > 41 and "left_fingerprint" not in data[key]:
            deleted += 1
            del data[key]
    # Save json file
    with json_file.open("w") as f:
        json.dump(data, f)
print(f"Deleted {deleted} entries.")
