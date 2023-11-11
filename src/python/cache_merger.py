""" Merge multiple caches into one 
Usage: python cache_merger.py cache1 cache2 cache3 --output_cache cache_merged
"""

import shutil
import json
from argparse import ArgumentParser
from pathlib import Path
from tqdm import tqdm
from typing import List



def merge_json_data(paths:List[Path], output_path:Path):
    """Merge multiple json files into one"""
    data = {}
    for path in paths:
        if path.exists():
            with path.open("r") as f:
                data.update(json.load(f))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(data, f, indent=4, sort_keys=True)


def copy_file(source:Path, destination:Path):
    """Copy a file from source to destination"""
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        print(destination)
        shutil.copy(source, destination)


def process_directory(directory:Path, other_caches:List[Path], output_cache:Path):
    """Process a directory recursively"""
    for path in tqdm(directory.rglob("*"), desc=f"Processing {directory}"):
        if path.is_file():
            # Skip the first part of the path (the cache name)
            relative_path = Path(*path.parts[1:])
            corresponding_paths = [
                cache / relative_path
                for cache in other_caches
                if (cache / relative_path).exists()
            ]
            if path.suffix == ".json":
                merge_json_data(
                    [path] + corresponding_paths, output_cache / relative_path
                )
            elif path.suffix != ".lock":
                copy_file(path, output_cache / relative_path)


def merge_caches(caches:List[Path], output_cache:Path):
    """Merge multiple caches into one"""
    if output_cache.exists():
        shutil.rmtree(output_cache)
    output_cache.mkdir(parents=True, exist_ok=True)

    for cache in caches:
        process_directory(cache, [c for c in caches if c != cache], output_cache)


if __name__ == "__main__":
    parser = ArgumentParser(description="Merge multiple caches into one")
    parser.add_argument("caches", type=Path, nargs="+", help="List of caches to merge")
    parser.add_argument(
        "--output_cache", type=Path, help="Output cache", default="cache_merged"
    )
    args = parser.parse_args()
    merge_caches(args.caches, args.output_cache)
