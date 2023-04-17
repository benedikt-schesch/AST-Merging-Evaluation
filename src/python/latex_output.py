#!/usr/bin/env python3
"""Output LaTeX tables and plots.

usage: python3 latex_output.py --input_csv <path_to_input>
                               --output_path <output_path>

This script takes a csv wiht all the results for each merge and merge tool.
It outputs all three tables in output_path for the latex file. All tables
should be copied into tables/ of the latex project.
"""


import sys
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from prettytable import PrettyTable
from merge_tester import MERGE_TOOLS

main_branch_names = ["main", "refs/heads/main", "master", "refs/heads/master"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_csv", type=str)
    parser.add_argument("--output_path", type=str)
    args = parser.parse_args()
    output_path = args.output_path
    Path(output_path).mkdir(parents=True, exist_ok=True)

    # open results file
    data = pd.read_csv(args.input_csv)
    for merge_tool in MERGE_TOOLS:
        data[merge_tool] = data[merge_tool].astype(int)

        # Filter out all data points that have any type of failure
        data = data[data[merge_tool] > 0]

    # figure 1 (stacked area)
    incorrect = []
    correct = []
    unhandled = []
    failure = []
    for merge_tool in MERGE_TOOLS:
        merge_tool_data = data[merge_tool]
        incorrect.append(sum(val in [3, 5, 126] for val in merge_tool_data))
        correct.append(sum(val == 2 for val in merge_tool_data))
        unhandled.append(sum(val == 1 for val in merge_tool_data))
        failure.append((val in [6, 124] for val in merge_tool_data))

    fig, ax = plt.subplots()

    ax.bar(MERGE_TOOLS, incorrect, label="Incorrect", color="#1F77B4")
    ax.bar(MERGE_TOOLS, unhandled, bottom=incorrect, label="Unhandled", color="#FF7F0E")
    ax.bar(
        MERGE_TOOLS,
        correct,
        label="Correct",
        bottom=[incorrect[i] + unhandled[i] for i in range(len(MERGE_TOOLS))],
        color="#2CA02C",
    )

    ax.set_ylabel("# of merges")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(reversed(handles), reversed(labels))

    plt.savefig(output_path + "/stacked.pdf")

    # table 1 (overall results)
    template = """\\begin{{tabular}}{{c|c c|c c|c c}}
            Tool & 
            \\multicolumn{{2}}{{|c|}}{{Correct Merges}} & 
            \\multicolumn{{2}}{{|c|}}{{Unhandled Merges}} &
            \\multicolumn{{2}}{{|c}}{{Incorrect Merges}}\\\\
            \\hline
            & \\# & \\% & \\# & \\% & \\# & \\%\\\\ \n"""

    total = len(data)
    args = []
    for merge_tool_idx, merge_tool in enumerate(MERGE_TOOLS):
        args.append(correct[merge_tool_idx])
        args.append(100 * correct[merge_tool_idx] / total if total != 0 else 0)
        args.append(unhandled[merge_tool_idx])
        args.append(100 * unhandled[merge_tool_idx] / total if total != 0 else 0)
        args.append(incorrect[merge_tool_idx])
        args.append(100 * incorrect[merge_tool_idx] / total if total != 0 else 0)
        template += (
            merge_tool.capitalize()
            + " & {} & {:.2f}\\% & {} & {:.2f}\\% & {} & {:.2f}\\%\\\\\n"
        )
    template += """\\end{{tabular}}"""

    table = template.format(*args)

    with open(output_path + "/table_summary.txt", "w") as file:
        file.write(table)

    # Printed Table

    my_table = PrettyTable()
    my_table.field_names = [
        "Merge Tool",
        "Correct Merges",
        "Unhandled Merges",
        "Incorrect Merges",
    ]
    for merge_tool_idx, merge_tool in enumerate(MERGE_TOOLS):
        my_table.add_row(
            [
                merge_tool,
                correct[merge_tool_idx],
                incorrect[merge_tool_idx],
                unhandled[merge_tool_idx],
            ]
        )

    print(my_table)
    if total == 0:
        sys.exit(0)

    # table 2 (by merge source)
    template2 = """\\begin{{tabular}}{{c|c c c c|c c c c|c c c c}}
            Tool & 
            \\multicolumn{{4}}{{|c|}}{{Correct Merges}} & 
            \\multicolumn{{4}}{{|c|}}{{Unhandled Merges}} &
            \\multicolumn{{4}}{{|c|}}{{Incorrect Merges}}\\\\
            &
            \\multicolumn{{2}}{{|c}}{{Main Branch}} & 
            \\multicolumn{{2}}{{c|}}{{Feature Branch}} &
            \\multicolumn{{2}}{{|c}}{{Main Branch}} & 
            \\multicolumn{{2}}{{c|}}{{Feature Branch}} &
            \\multicolumn{{2}}{{|c}}{{Main Branch}} & 
            \\multicolumn{{2}}{{c|}}{{Feature Branch}} &
            \\hline
            & \\# & \\% & \\# & \\% & \\# & \\% & \\# & \\% & \\# & \\% & \\# & \\%\\\\ \n"""

    main = data[data["branch_name"].isin(main_branch_names)]
    feature = data[~data["branch_name"].isin(main_branch_names)]

    args = []
    for merge_tool_idx, merge_tool in enumerate(MERGE_TOOLS):
        mergem = main[merge_tool]
        mergef = feature[merge_tool]

        correct = sum(val == 2 for val in mergem)
        args.append(correct)
        args.append(100 * correct / len(main) if len(main) != 0 else 0)
        correct = sum(val == 2 for val in mergef)
        args.append(correct)
        args.append(100 * correct / len(feature) if len(feature) > 0 else -1)

        unhandled = sum(val == 1 for val in mergem)
        args.append(unhandled)
        args.append(100 * unhandled / len(main) if len(main) != 0 else 0)
        unhandled = sum(val == 1 for val in mergef)
        args.append(unhandled)
        args.append(100 * unhandled / len(feature) if len(feature) > 0 else -1)

        incorrect = sum(val in [3, 5, 126] for val in mergem)
        args.append(incorrect)
        args.append(100 * incorrect / len(main) if len(main) != 0 else 0)
        incorrect = sum(val in [3, 5, 126] for val in mergef)
        args.append(incorrect)
        args.append(100 * incorrect / len(feature) if len(feature) > 0 else -1)

        template2 += (
            "            "
            + merge_tool.capitalize()
            + " & {} & {:.2f}\\% & {} & {:.2f}\\% & {} & {:.2f}\\% & {} & \
                {:.2f}\\% & {} & {:.2f}\\% & {} & {:.2f}\\%\\\\ \n"
        )

    template2 += """\\end{{tabular}}"""

    table2 = template2.format(*args)

    with open(output_path + "/table_feature_main_summary.txt", "w") as file:
        file.write(table2)

    # table 3 (by merge source)
    res = " & ".join(["{:.1f}" for _ in MERGE_TOOLS])
    template3 = """\\begin{{tabular}}{{c|c|c|c}}
        & Git Merge & Spork & IntelliMerge\\\\
        \\hline \n"""
    template3 += """\tMean runtime &""" + res + """\\\\ \n"""
    template3 += """\tMedian runtime &""" + res + """\\\\ \n"""
    template3 += (
        """\tMax runtime &"""
        + res
        + """\\\\
        \\end{{tabular}}"""
    )

    main = data[data["branch_name"].isin(main_branch_names)]
    feature = data[~data["branch_name"].isin(main_branch_names)]

    args = []
    for f in [np.mean, np.median, np.max]:
        for merge_tool in MERGE_TOOLS:
            args.append(f(data[merge_tool + " runtime"]))
    table3 = template3.format(*args)

    with open(output_path + "/table_runtime.txt", "w") as file:
        file.write(table3)
