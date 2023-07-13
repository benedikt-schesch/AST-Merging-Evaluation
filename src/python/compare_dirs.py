#!/usr/bin/env python3
"""Compare the contents of two directories

usage: python3 compare_dirs.py <path_to_dir1> <path_to_dir2>

Exits with 1 if the lists of contained files don't match
Exits with 1 and prints the first file whose contents don't 
match if one exists
Exits with 0 if the contents of the directories are identical (in 
terms of files - empty subdirectories are not considered)
"""

import sys
import os

if len(sys.argv) != 3:
    sys.stderr.write("Error: script takes 2 paths as parameters")
    sys.exit(1)

path1 = sys.argv[1]
path2 = sys.argv[2]

# compute list of files for path1
dirs = []
files1 = set()
# top level files and dirs
for entry in os.listdir(path1):
    path = os.path.join(path1, entry)
    if os.path.isdir(path):
        dirs.append(entry)
    elif os.path.isfile(path):
        files1.add(entry)
# recursive files and dirs
while dirs:
    currdir = dirs.pop()
    dirpath = os.path.join(path1, currdir)
    for entry in os.listdir(dirpath):
        path = os.path.join(dirpath, entry)
        if os.path.isdir(path):
            dirs.append(os.path.join(currdir, entry))
        elif os.path.isfile(path):
            files1.add(os.path.join(currdir, entry))

# compute list of files for path2
dirs = []
files2 = set()
for entry in os.listdir(path2):
    path = os.path.join(path2, entry)
    if os.path.isdir(path):
        dirs.append(entry)
    elif os.path.isfile(path):
        files2.add(entry)
while dirs:
    currdir = dirs.pop()
    dirpath = os.path.join(path2, currdir)
    for entry in os.listdir(dirpath):
        path = os.path.join(dirpath, entry)
        if os.path.isdir(path):
            dirs.append(os.path.join(currdir, entry))
        elif os.path.isfile(path):
            files2.add(os.path.join(currdir, entry))

# file lists for equal dirs
if files1 != files2:
    print("files lists don't match")
    sys.exit(1)

# compare files one by one
for entry in files1:
    with open(os.path.join(path1, entry), "r") as file1:
        with open(os.path.join(path2, entry), "r") as file2:
            lines1 = file1.readlines()
            lines2 = file2.readlines()
            if lines1 != lines2:
                print(entry)
                sys.exit(1)

sys.exit(0)
