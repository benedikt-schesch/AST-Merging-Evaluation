#! /usr/bin/env python

# This is a helper script for `resolve-adjacent-conflicts` and
# `resolve-import-conflicts`.

"""Edits a file in place to remove certain conflict markers.

Usage: resolve-conflicts.py [options] <filenme>

--java_imports: Resolves conflicts related to Java import statements
The output includes every `import` statements that is in either of the parents.

--adjacent_lines: Resolves conflicts on adjacent lines, by accepting both edits.

Exit status is 0 (success) if no conflicts remain.
Exit status is 1 (failure) if conflicts remain.
"""

from argparse import ArgumentParser
import itertools
import os
import shutil
import sys
import tempfile
from typing import List, Union, Tuple


def main():  # pylint: disable=too-many-locals
    """The main entry point."""
    arg_parser = ArgumentParser()
    arg_parser.add_argument("filename")
    arg_parser.add_argument(
        "--java_imports",
        action="store_true",
        help="If set, resolve conflicts related to Java import statements",
    )
    arg_parser.add_argument(
        "--adjacent_lines",
        action="store_true",
        help="If set, resolve conflicts on adjacent lines",
    )
    args = arg_parser.parse_args()
    filename = args.filename

    with open(filename) as file:
        lines = file.readlines()

    # Exit status 0 means no conflicts remain, 1 means some merge conflict remains.
    conflicts_remain = False
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
        file_len = len(lines)
        i = 0
        while i < file_len:
            conflict = looking_at_conflict(filename, i, lines)
            if conflict is None:
                tmp.write(lines[i])
                i = i + 1
            else:
                (base, parent1, parent2, num_lines) = conflict
                merged = merge(
                    base, parent1, parent2, args.java_imports, args.adjacent_lines
                )
                if merged is None:
                    tmp.write(lines[i])
                    i = i + 1
                    conflicts_remain = True
                else:
                    for line in merged:
                        tmp.write(line)
                    i = i + num_lines

        tmp.close()
        shutil.copy(tmp.name, filename)
        os.unlink(tmp.name)

    if conflicts_remain:
        sys.exit(1)
    else:
        sys.exit(0)


def looking_at_conflict(  # pylint: disable=too-many-return-statements
    filename: str, start_index: int, lines: List[str]
) -> Union[None, Tuple[List[str], List[str], List[str], int]]:
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
                + str(start_index)
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
                    + str(start_index)
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
                + str(start_index)
                + ", did not find >>>>>>> in "
                + filename
            )
            return None
    index = index + 1

    return (base, parent1, parent2, index - start_index)


def merge(
    base: List[str],
    parent1: List[str],
    parent2: List[str],
    java_imports: bool,
    adjacent_lines: bool,
) -> Union[List[str], None]:
    """Given text for the base and two parents, return merged text.

    Args:
        base: a list of lines
        parent1: a list of lines
        parent2: a list of lines

    Returns:
        a list of lines, or None if it cannot do merging.
    """

    print(base, parent1, parent2)

    if java_imports:
        if (
            all_import_lines(base)
            and all_import_lines(parent1)
            and all_import_lines(parent2)
        ):
            # A simplistic merge that retains all import lines in either parent.
            return list(set(parent1 + parent2)).sort()

    if adjacent_lines:
        adjacent_line_merge = merge_edits_on_different_lines(base, parent1, parent2)
        if adjacent_line_merge is not None:
            return adjacent_line_merge

    return None


def all_import_lines(lines: List[str]) -> bool:
    """Return true if every given line is a Java import line or is blank."""
    return all(line.startswith("import ") or line.strip() == "" for line in lines)


def merge_edits_on_different_lines(
    base, parent1: List[str], parent2: List[str]
) -> Union[List[str], None]:
    """Return a merged version, if at most parent1 or parent2 edits each line.
    Otherwise, return None.
    """

    print("Entered merge_edits_on_different_lines")

    ### No lines are added or removed, only modified.
    base_len = len(base)
    result = None
    if base_len == len(parent1) and base_len == len(parent2):
        result = []
        for base_line, parent1_line, parent2_line in itertools.zip_longest(
            base, parent1, parent2
        ):
            print("Considering line:", base_line, parent1_line, parent2_line)
            if parent1_line == parent2_line:
                result.append(parent1_line)
            elif base_line == parent1_line:
                result.append(parent2_line)
            elif base_line == parent2_line:
                result.append(parent1_line)
            else:
                result = None
                break
        print("merge_edits_on_different_lines =>", result)
    if result is not None:
        print("merge_edits_on_different_lines =>", result)
        return result

    ### Deletions at the beginning or end.
    if base_len != 0:
        result = merge_base_is_prefix_or_suffix(base, parent1, parent2)
        if result is None:
            result = merge_base_is_prefix_or_suffix(base, parent2, parent1)
        if result is not None:
            return result

    ### Interleaved deletions, with an empty merge outcome.
    if base_len != 0:
        if is_subsequence(parent1, base) and is_subsequence(parent2, base):
            return []

    print("merge_edits_on_different_lines =>", result)
    return result


def merge_base_is_prefix_or_suffix(
    base: List[str], parent1: List[str], parent2: List[str]
) -> Union[List[str], None]:
    """Special cases when the base is a prefix or suffix of parent1.
    That is, parent1 is pure additions at the beginning or end of base.  Parent2
    deleted all the lines, possibly replacing them by something else.  (We know
    this because there is no common line in base and parent2.  If there were, it
    would also be in parent1, and the hunk would have been split into two at the
    common line that's in all three texts.)
    We know the relative position of the additions in parent1.
    """
    base_len = len(base)
    parent1_len = len(parent1)
    parent2_len = len(parent2)
    if base_len < parent1_len:
        if parent1[:base_len] == base:
            print("startswith", parent1, base)
            return parent2 + parent1[base_len:]
        if parent1[-base_len:] == base:
            print("endswith", parent1, base)
            return parent1[:-base_len] + parent2
    return None


def is_subsequence(s1: List[T], s2: List[T]) -> bool:
    """Returns true if s1 is subsequence of s2."""

    # Iterative implementation.

    n, m = len(s1), len(s2)
    i, j = 0, 0
    while i < n and j < m:
        if s1[i] == s2[j]:
            i += 1
        j += 1

    # If i reaches end of s1, we found all characters of s1 in s2,
    # so s1 is a subsequence of s2.
    return i == n


if __name__ == "__main__":
    main()
