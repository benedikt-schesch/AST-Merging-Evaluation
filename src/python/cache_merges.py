# Merge two caches into one in json format
# Usage: python cache_merges.py <cache1> <cache2> <output>

import sys
import json


def main():
    if len(sys.argv) != 4:
        print("Usage: python cache_merges.py <cache1> <cache2> <output>")
        return

    cache1 = sys.argv[1]
    cache2 = sys.argv[2]
    output = sys.argv[3]

    with open(cache1) as f:
        data1 = json.load(f)

    with open(cache2) as f:
        data2 = json.load(f)

    data1.update(data2)

    with open(output, "w") as f:
        json.dump(data1, f)
