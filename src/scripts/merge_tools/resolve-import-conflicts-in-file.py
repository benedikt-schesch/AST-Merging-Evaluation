#! /usr/bin/env python3
# TODO: Benedikt, could you review and improve this file?  I'm sure it is not perfect Python style.

"""Edits a file in place to remove conflict markers related to Java imports.
It simplistically leaves all the imports that appear in either parent.
"""


# TODO: merge both scripts into one.

import shutil
import argparse
from pathlib import Path
import tempfile
from typing import List, Union, Tuple


def all_import_lines(lines: List[str]) -> bool:
    """Return true if every line is a Java import line."""
    return all(line.startswith("import ") for line in lines)


def merge(base, parent1: List[str], parent2: List[str]) -> Union[List[str], None]:
    """Given text for the base and two parents, return merged text.

    This currently does a simplistic merge that retains all lines in either parent.

    Args:
        base: a list of lines
        parent1: a list of lines
        parent2: a list of lines

    Returns:
        Union[List[str], None]: If the merge is successful, returns a list of lines.
    """

    if (
        all_import_lines(base)
        and all_import_lines(parent1)
        and all_import_lines(parent2)
    ):
        return parent1 + parent2

    return None


def looking_at_conflict(  # pylint: disable=too-many-return-statements
    file: Path, start_index: int, lines: List[str]
) -> Union[None, Tuple[List[str], List[str], List[str], int]]:
    """Tests whether the text starting at line `start_index` is the beginning of a conflict.
    If not, returns None.
    If so, returns a 4-tuple of (base, parent1, parent2, num_lines_in_conflict)
    where the first 3 elements of the tuple are lists of lines.
    Args:
        start_index: an index into `lines`.
        lines: all the lines of the file with name `file`.
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
                + str(start_index)
                + ", did not find ||||||| or ======= in "
                + str(file)
            )
            return None
    if lines[index].startswith("|||||||"):
        index = index + 1
        if index == num_lines:
            print("File ends with |||||||: " + str(file))
            return None
        while not lines[index].startswith("======="):
            base.append(lines[index])
            index = index + 1
            if index == num_lines:
                print(
                    "Starting at line "
                    + str(start_index)
                    + ", did not find ======= in "
                    + str(file)
                )
                return None
    assert lines[index].startswith("=======")
    index = index + 1  # skip over "=======" line
    if index == num_lines:
        print("File ends with =======: " + str(file))
        return None
    while not lines[index].startswith(">>>>>>>"):
        parent2.append(lines[index])
        index = index + 1
        if index == num_lines:
            print(
                "Starting at line "
                + str(start_index)
                + ", did not find >>>>>>> in "
                + str(file)
            )
            return None
    index = index + 1

    return (base, parent1, parent2, index - start_index)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path)
    args = parser.parse_args()

    with open(args.file) as file:
        lines = file.readlines()

    with tempfile.NamedTemporaryFile(mode="w", delete=True) as tmp:
        file_len = len(lines)
        i = 0
        while i < file_len:
            conflict = looking_at_conflict(Path(args.file), i, lines)
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

        # Copying the file back to the original location
        shutil.copyfile(tmp.name, args.file)
