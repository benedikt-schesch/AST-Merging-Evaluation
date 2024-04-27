#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deletes all placeholders from the cache. Placeholders are created when a
a process starts; it indicates that is has started and is still running.
If the process fails, the placeholder is not replaced with the actual
result. This script deletes all placeholders from the cache.

Usage:
    python delete_cache_placeholders.py --cache_directory <path_to_cache>

Args:
    cache_directory (str): Path to cache directory
"""

from argparse import ArgumentParser
from pathlib import Path
import json

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--cache_dir", help="Path to cache directory", default="cache", type=Path
    )
    args = parser.parse_args()

    cache_directory = Path(args.cache_dir)

    n_deleted = 0
    for file in cache_directory.glob("**/*.json"):
        if file.is_dir():
            continue
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"Could not read {file}")
            file.unlink()
            continue

        for key in list(data.keys()):
            if data[key] is None:
                data.pop(key)
                n_deleted += 1

        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, sort_keys=True)
    print(f"Deleted {n_deleted} placeholders")
