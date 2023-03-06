#!/usr/bin/env python3
"""Output latex tables and plots."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from prettytable import PrettyTable


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--result_path", type=str)
    parser.add_argument("--output_path", type=str)
    args = parser.parse_args()
    output_path = args.output_path
    Path(output_path).mkdir(parents=True, exist_ok=True)

    # open results file
    data = pd.read_csv(args.result_path)
    data["gitmerge"] = data["gitmerge"].astype(int)
    data["spork"] = data["spork"].astype(int)
    data["intellimerge"] = data["intellimerge"].astype(int)

    data = data[
        (data["gitmerge"] > 0) & (data["spork"] > 0) & (data["intellimerge"] > 0)
    ]

    gitmerge = data["gitmerge"]
    spork = data["spork"]
    intellimerge = data["intellimerge"]

    gitmergeincorrect = sum(val in [3, 5, 126] for val in gitmerge)
    gitmergecorrect = sum(val == 2 for val in gitmerge)
    gitmergeunhandled = sum(val == 1 for val in gitmerge)
    gitmergefailure = sum(val in [6, 124] for val in gitmerge)

    sporkincorrect = sum(val in [3, 5, 126] for val in spork)
    sporkcorrect = sum(val == 2 for val in spork)
    sporkunhandled = sum(val == 1 for val in spork)
    sporkfailure = sum(val in [6, 124] for val in spork)

    intellimergeincorrect = sum(val in [3, 5, 126] for val in intellimerge)
    intellimergecorrect = sum(val == 2 for val in intellimerge)
    intellimergeunhandled = sum(val == 1 for val in intellimerge)
    intellimergefailure = sum(val in [6, 124] for val in intellimerge)

    # figure 1 (stacked area)
    tools = ["Git Merge", "Spork", "IntelliMerge"]
    incorrect = [gitmergeincorrect, sporkincorrect, intellimergeincorrect]
    unhandled = [gitmergeunhandled, sporkunhandled, intellimergeunhandled]
    correct = [gitmergecorrect, sporkcorrect, intellimergecorrect]
    failure = [gitmergefailure, sporkfailure, intellimergefailure]

    fig, ax = plt.subplots()

    ax.bar(tools, incorrect, label="Incorrect", color="#1F77B4")
    ax.bar(tools, unhandled, bottom=incorrect, label="Unhandled", color="#FF7F0E")
    ax.bar(
        tools,
        correct,
        label="Correct",
        bottom=[incorrect[i] + unhandled[i] for i in range(len(tools))],
        color="#2CA02C",
    )

    ax.set_ylabel("# of merges")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(reversed(handles), reversed(labels))

    plt.savefig(output_path + "/stacked.pdf")

    # table 1 (overall results)
    template = """\\begin{{tabular}}{{c|c c|c c|c c}}
            Tool & 
            \multicolumn{{2}}{{|c|}}{{Correct Merges}} & 
            \multicolumn{{2}}{{|c|}}{{Unhandled Merges}} &
            \multicolumn{{2}}{{|c}}{{Incorrect Merges}}\\\\
            \hline
            & \# & \% & \# & \% & \# & \%\\\\ 
            Git Merge & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\%\\\\
            Spork & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\%\\\\
            IntelliMerge & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\%\\\\
        \end{{tabular}}"""

    total = len(data)
    args = []
    for i in range(len(tools)):
        args.append(correct[i])
        args.append(100 * correct[i] / total if total != 0 else 0)
        args.append(unhandled[i])
        args.append(100 * unhandled[i] / total if total != 0 else 0)
        args.append(incorrect[i])
        args.append(100 * incorrect[i] / total if total != 0 else 0)

    my_table = PrettyTable()
    my_table.field_names = [
        "Merge Tool",
        "Correct Merges",
        "Unhandled Merges",
        "Incorrect Merges",
    ]
    my_table.add_row(
        ["Git Merge", gitmergecorrect, gitmergeincorrect, gitmergeunhandled]
    )
    my_table.add_row(["Spork", sporkcorrect, sporkincorrect, sporkunhandled])
    my_table.add_row(
        [
            "IntelliMerge",
            intellimergecorrect,
            intellimergeincorrect,
            intellimergeunhandled,
        ]
    )
    print(my_table)

    table = template.format(*args)

    with open(output_path + "/table1.txt", "w") as file:
        file.write(table)

    # table 2 (by merge source)
    template2 = """\\begin{{tabular}}{{c|c c c c|c c c c|c c c c}}
            Tool & 
            \multicolumn{{4}}{{|c|}}{{Correct Merges}} & 
            \multicolumn{{4}}{{|c|}}{{Unhandled Merges}} &
            \multicolumn{{4}}{{|c|}}{{Incorrect Merges}}\\\\
            &
            \multicolumn{{2}}{{|c}}{{Main Branch}} & 
            \multicolumn{{2}}{{c|}}{{Feature Branch}} &
            \multicolumn{{2}}{{|c}}{{Main Branch}} & 
            \multicolumn{{2}}{{c|}}{{Feature Branch}} &
            \multicolumn{{2}}{{|c}}{{Main Branch}} & 
            \multicolumn{{2}}{{c|}}{{Feature Branch}} &
            \hline
            & \# & \% & \# & \% & \# & \% & \# & \% & \# & \% & \# & \%\\\\ 
            Git Merge & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\%\\\\
            Spork & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\%\\\\
            IntelliMerge & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\%\\\\
        \end{{tabular}}"""

    main = data[(data["branch_name"] == "main") | (data["branch_name"] == "master")]
    feature = data[(data["branch_name"] != "main") & (data["branch_name"] != "master")]

    gitmergem = main["gitmerge"]
    sporkm = main["spork"]
    intellimergem = main["intellimerge"]
    gitmergef = feature["gitmerge"]
    sporkf = feature["spork"]
    intellimergef = feature["intellimerge"]
    m = [gitmergem, sporkm, intellimergem]
    f = [gitmergef, sporkf, intellimergef]

    args = []
    for i in range(len(tools)):
        correct = sum(val == 2 for val in m[i])
        args.append(correct)
        args.append(100 * correct / len(main) if len(main) != 0 else 0)
        correct = sum(val == 2 for val in f[i])
        args.append(correct)
        args.append(100 * correct / len(feature) if len(feature) > 0 else -1)

        unhandled = sum(val == 1 for val in m[i])
        args.append(unhandled)
        args.append(100 * unhandled / len(main)  if len(main) != 0 else 0)
        unhandled = sum(val == 1 for val in f[i])
        args.append(unhandled)
        args.append(100 * unhandled / len(feature) if len(feature) > 0 else -1)

        incorrect = sum(val in [3, 5, 126] for val in m[i])
        args.append(incorrect)
        args.append(100 * incorrect / len(main) if len(main) != 0 else 0)
        incorrect = sum(val in [3, 5, 126] for val in f[i])
        args.append(incorrect)
        args.append(100 * incorrect / len(feature) if len(feature) > 0 else -1)

    table2 = template2.format(*args)

    with open(output_path + "/table2.txt", "w") as file:
        file.write(table2)
