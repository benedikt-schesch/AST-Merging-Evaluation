#!/usr/bin/env python

"""Remove all columns whose name contains "run_time"."""

import csv
import os
import sys

args = sys.argv[1:]

if len(args) != 2:
    print(
        "Usage:", os.path.basename(__file__), "with-run-times.csv without-run-times.csv"
    )
    sys.exit(1)

# From https://stackoverflow.com/questions/74898724
with open(args[0], "r", newline="") as input_file, open(args[1], "w") as output_file:
    reader = csv.reader(input_file)
    writer = csv.writer(output_file, lineterminator="\n")

    header_row = next(reader)

    run_time_columns = [col for col in header_row if "run_time" in col]

    run_time_column_indices = [header_row.index(col) for col in run_time_columns]

    new_header_row = [col for col in header_row if col not in run_time_columns]

    writer.writerow(new_header_row)

    for row in reader:
        new_row = [row[i] for i in range(len(row)) if i not in run_time_column_indices]

        writer.writerow(new_row)
