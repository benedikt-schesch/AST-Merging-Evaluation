# usage: python3 compare_dirs.py <path1> <path2>

import sys
import os

if len(sys.argv) != 3:
    sys.stderr.write("Error: script takes 2 paths as parameters");
    exit(1)

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
    exit(1)

# compare files one by one
for entry in files1:
    file1 = open(os.path.join(path1, entry), "r")
    file2 = open(os.path.join(path2, entry), "r")
    lines1 = file1.readlines()
    lines2 = file2.readlines()
    file1.close()
    file2.close()
    if lines1 != lines2:
        print(entry)
        exit(1)

exit(0)
