""" 
Deletes all placeholders from the cache. Placeholders are created when a
a process starts it indicates that is has started and is still running.
If the process fails, the placeholder is not replaced with the actual
result. This script deletes all placeholders from the cache.

Usage:
    python clean_cache_placeholders.py --cache_path <path_to_cache>

Args:
    cache_path (str): Path to cache directory
"""

from argparse import ArgumentParser
from pathlib import Path
import json

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--cache_dir", help="Path to cache directory", default="cache")
    args = parser.parse_args()

    cache_path = Path(args.cache_dir)

    n_deleted = 0
    for file in cache_path.glob("**/*.json"):
        with open(file, "r") as f:
            data = json.load(f)

        for key in list(data.keys()):
            if data[key] is None:
                data.pop(key)
                n_deleted += 1

        with open(file, "w") as f:
            json.dump(data, f, indent=4)
    print(f"Deleted {n_deleted} placeholders")