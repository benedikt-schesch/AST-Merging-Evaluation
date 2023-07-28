<<<<<<< HEAD
#! /usr/bin/env python

# Edits a file in place to remove conflict markers related to Java imports.


# TODO: merge both scripts into one.

import os
import sys
import tempfile

if len(sys.argv) != 2:
    print("Provide exactly one command-line argument")
    sys.exit(1)

filename = sys.argv[1]
print("filename = " + filename)
with open(filename) as file:
    lines = file.readlines()

# The state is: nonconflict, in left, in original, in right.
state = "nonconflict"


def merge(base, parent1, parent2):
    """Given text for the base and two parents, return merged text.

    Args:
        base: a list of lines
        parent1: a list of lines
        parent2: a list of lines

    Returns:
        a list of lines, or None if it cannot do merging.
    """

    return None


def looking_at_conflict(start_index, lines):
    """Tests whether the following text starts a conflict.
    If not, returns None.
    If so, returns a 3-tuple of lists of lines (base, parent1, parent2, num_lines_in_conflict).
    """

    if not lines[start_index].startswith("<<<<<<<"):
        return None

    base = []
    parent1 = []
    parent2 = []

    ## This may will crash if the file is malformed!

    num_lines
    index = start_index + 1
    if index == num_lines:
        return None
    while not (
        lines[index].startswith("|||||||") or lines[index].startswith("=======")
    ):
        parent1.append(lines[index])
        index = index + 1
        if index == num_lines:
            print(
                "Starting at line "
                + start_index
                + ", did not find ||||||| or ======= in "
                + filename
            )
            return None
    if lines[index].startswith("|||||||"):
        index = index + 1
        if index == num_lines:
            print("File ends with |||||||: " + filename)
            return None
        while not (lines[index].startswith("=======")):
            base.append(lines[index])
            index = index + 1
            if index == num_lines:
                print(
                    "Starting at line "
                    + start_index
                    + ", did not find ======= in "
                    + filename
                )
                return None
    assert lines[index].startswith("=======")
    index = index + 1  # skip over "=======" line
    if index == num_lines:
        print("File ends with =======: " + filename)
        return None
    while not (lines[index].startswith(">>>>>>>")):
        parent2.append(lines[index])
        index = index + 1
        if index == num_lines:
            print(
                "Starting at line "
                + start_index
                + ", did not find >>>>>>> in "
                + filename
            )
            return None
    index = index + 1

    return (base, parent1, parent2, index - start_index)


with tempfile.NamedTemporaryFile(mode="w") as tmp:
    file_len = len(lines)
    i = 0
    while i < file_len:
        conflict = looking_at_conflict(i, lines)
        if conflict is None:
            tmp.write(lines[i])
            i = i + 1
        else:
            (base, parent1, parent2) = conflict
            merged = merge(base, parent1, parent2, num_lines)
            if merged is None:
                tmp.write(lines[i])
                i = i + 1
            else:
                for line in merged:
                    tmp.write(line)
                i = i + num_lines

    tmp.close()
    os.replace(tmp.name, filename)
||||||| parent of 47cadfb2d (resolve-import-conflicts scripts)
=======
#! /usr/bin/env python

"""Edits a file in place to remove conflict markers related to Java imports."""


# TODO: merge both scripts into one.

import os
import shutil
import sys
import tempfile

if len(sys.argv) != 2:
    print("Provide exactly one command-line argument")
    sys.exit(1)

filename = sys.argv[1]
with open(filename) as file:
    lines = file.readlines()

# The state is: nonconflict, in left, in original, in right.
state = "nonconflict"


def all_import_lines(lines):
    """Return true if every line is a Java import line."""
    return all(line.startswith("import ") for line in lines)


def merge(base, parent1, parent2):
    """Given text for the base and two parents, return merged text.

    This currently does a simplistic merge that retains all lines in either parent.

    Args:
        base: a list of lines
        parent1: a list of lines
        parent2: a list of lines

    Returns:
        a list of lines, or None if it cannot do merging.
    """

    if (
        all_import_lines(base)
        and all_import_lines(parent1)
        and all_import_lines(parent2)
    ):
        return parent1 + parent2

    return None


def looking_at_conflict(start_index, lines):  # pylint: disable=R0911
    """Tests whether the following text starts a conflict.
    If not, returns None.
    If so, returns a 4-tuple of (base, parent1, parent2, num_lines_in_conflict)
    where the first 3 elements of the tuple are lists of lines.
    """

    if not lines[start_index].startswith("<<<<<<<"):
        return None

    base = []
    parent1 = []
    parent2 = []

    num_lines = len(lines)
    index = start_index + 1
    if index == num_lines:
        return None
    while not (
        lines[index].startswith("|||||||") or lines[index].startswith("=======")
    ):
        parent1.append(lines[index])
        index = index + 1
        if index == num_lines:
            print(
                "Starting at line "
                + start_index
                + ", did not find ||||||| or ======= in "
                + filename
            )
            return None
    if lines[index].startswith("|||||||"):
        index = index + 1
        if index == num_lines:
            print("File ends with |||||||: " + filename)
            return None
        while not lines[index].startswith("======="):
            base.append(lines[index])
            index = index + 1
            if index == num_lines:
                print(
                    "Starting at line "
                    + start_index
                    + ", did not find ======= in "
                    + filename
                )
                return None
    assert lines[index].startswith("=======")
    index = index + 1  # skip over "=======" line
    if index == num_lines:
        print("File ends with =======: " + filename)
        return None
    while not lines[index].startswith(">>>>>>>"):
        parent2.append(lines[index])
        index = index + 1
        if index == num_lines:
            print(
                "Starting at line "
                + start_index
                + ", did not find >>>>>>> in "
                + filename
            )
            return None
    index = index + 1

    return (base, parent1, parent2, index - start_index)


with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
    file_len = len(lines)
    i = 0
    while i < file_len:
        conflict = looking_at_conflict(i, lines)
        if conflict is None:
            tmp.write(lines[i])
            i = i + 1
        else:
            (base, parent1, parent2, num_lines) = conflict
            merged = merge(base, parent1, parent2)
            if merged is None:
                tmp.write(lines[i])
                i = i + 1
            else:
                for line in merged:
                    tmp.write(line)
                i = i + num_lines

    tmp.close()
    shutil.copy(tmp.name, filename)
    os.unlink(tmp.name)
>>>>>>> 47cadfb2d (resolve-import-conflicts scripts)
