#!/usr/bin/env python3
"""Output LaTeX tables and plots.

usage: python3 latex_output.py --input_csv <path_to_input>
                               --output_path <output_path>

This script takes a csv with all the results for each merge and merge tool.
It outputs all three tables in output_path for the latex file. All tables
should be copied into tables/ of the latex project.
"""


import os
import argparse
from pathlib import Path
from functools import partial

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import pandas as pd
from prettytable import PrettyTable
from merge_tester import MERGE_TOOL, MERGE_STATE
from tqdm import tqdm
import seaborn as sns

matplotlib.use("pgf")
matplotlib.rcParams.update(
    {
        "pgf.texsystem": "pdflatex",
        "font.family": "serif",
        "text.usetex": True,
        "pgf.rcfonts": False,
    }
)

MERGE_FAILURE_NAMES = [
    MERGE_STATE.Tests_exception.name,
    MERGE_STATE.Tests_timedout.name,
]

MERGE_UNHANDLED_NAMES = [
    MERGE_STATE.Merge_failed.name,
    MERGE_STATE.Merge_timedout.name,
    MERGE_STATE.Merge_exception.name,
]


def compute_inconsistent_merge_results(df: pd.DataFrame):
    """Compute inconsistent merge results.
    Args:
        df: dataframe containing the merge results
    Returns:
        list of inconsistent merge results
    """
    inconsistent_merge_results = []
    for _, row in tqdm(df.iterrows(), total=len(df)):
        n_failures = 0
        for i in MERGE_TOOL:
            if row[f"{i}"] in MERGE_FAILURE_NAMES:
                n_failures += 1
        if 0 < n_failures < len(MERGE_TOOL):
            inconsistent_merge_results.append(row)
    return inconsistent_merge_results


main_branch_names = ["main", "refs/heads/main", "master", "refs/heads/master"]


def check_triangle_constraint(row):
    """Check triangle constraint.
    Args:
        row: row of the dataframe
    Returns:
        True if the triangle constraint is broken, False otherwise
    """
    for idx1, mt1 in enumerate(MERGE_TOOL):
        if row[mt1] in (
            MERGE_STATE.Merge_failed.name,
            MERGE_STATE.Merge_timedout.name,
            MERGE_STATE.Merge_exception.name,
        ):
            continue
        for idx2, mt2 in enumerate(MERGE_TOOL[idx1 + 1 :]):
            if row[mt2] in (
                MERGE_STATE.Merge_failed.name,
                MERGE_STATE.Merge_timedout.name,
                MERGE_STATE.Merge_exception.name,
            ):
                continue
            for idx3, mt3 in enumerate(MERGE_TOOL[idx1 + idx2 + 2 :]):
                if row[mt3] in (
                    MERGE_STATE.Merge_failed.name,
                    MERGE_STATE.Merge_timedout.name,
                    MERGE_STATE.Merge_exception.name,
                ):
                    continue
                name1 = f"Equivalent {mt1} {mt2}"
                name2 = f"Equivalent {mt2} {mt3}"
                name3 = f"Equivalent {mt1} {mt3}"
                if name1 in row and name2 in row and name3 in row:
                    if row[name1] and row[name2] and not row[name3]:
                        return True
                    if row[name1] and not row[name2] and row[name3]:
                        return True
                    if not row[name1] and row[name2] and row[name3]:
                        return True
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_csv", type=str, default="results/result.csv")
    parser.add_argument("--output_path", type=str, default="results")
    args = parser.parse_args()
    output_path = args.output_path
    plots_output_path = os.path.join(output_path, "plots")
    tables_output_path = os.path.join(output_path, "tables")
    Path(plots_output_path).mkdir(parents=True, exist_ok=True)
    Path(tables_output_path).mkdir(parents=True, exist_ok=True)

    # open results file
    result_df = pd.read_csv(args.input_csv, index_col="idx")
    old_len = len(result_df)
    inconsistent_merge_results = compute_inconsistent_merge_results(result_df)
    print(
        "Number of inconsistent entries that will be ignored:",
        len(inconsistent_merge_results),
    )
    for row in tqdm(inconsistent_merge_results):
        result_df.drop(row.name, inplace=True)
    assert old_len - len(result_df) == len(inconsistent_merge_results)

    # Check triangle equalities
    count = 0
    for _, row in tqdm(result_df.iterrows(), total=len(result_df)):
        count += check_triangle_constraint(row)
    print("Number of triangle broken triangle equalities:", count)

    # Figure (Heat Map diffing)
    result = np.zeros((len(MERGE_TOOL), len(MERGE_TOOL)))
    for _, row in tqdm(result_df.iterrows()):
        for idx, merge_tool1 in enumerate(MERGE_TOOL):
            for idx2, merge_tool2 in enumerate(MERGE_TOOL[(idx + 1) :]):
                if (
                    not row[f"Equivalent {merge_tool1} {merge_tool2}"]
                    and row[merge_tool1]
                    not in (
                        MERGE_STATE.Merge_failed.name,
                        MERGE_STATE.Merge_timedout.name,
                        MERGE_STATE.Merge_exception.name,
                    )
                    and row[merge_tool2]
                    not in (
                        MERGE_STATE.Merge_failed.name,
                        MERGE_STATE.Merge_timedout.name,
                        MERGE_STATE.Merge_exception.name,
                    )
                ):
                    result[idx][idx2 + idx + 1] += 1
                    result[idx2 + idx + 1][idx] += 1
    fig, ax = plt.subplots()
    result = np.tril(result)
    latex_merge_tool = ["$" + i.capitalize() + "$" for i in MERGE_TOOL]
    heatmap = sns.heatmap(
        result,
        annot=True,
        ax=ax,
        xticklabels=latex_merge_tool,
        yticklabels=latex_merge_tool,
        fmt="g",
        mask=result == 0,
        cmap="Blues",
    )
    heatmap.set_yticklabels(labels=heatmap.get_yticklabels(), va="center")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_output_path, "heatmap.pdf"))

    # figure 1 (stacked area)
    incorrect = []
    correct = []
    unhandled = []
    failure = []
    for merge_tool in MERGE_TOOL:
        merge_tool_status = result_df[merge_tool]
        correct.append(
            sum(val == MERGE_STATE.Tests_passed.name for val in merge_tool_status)
        )
        incorrect.append(
            sum(val == MERGE_STATE.Tests_failed.name for val in merge_tool_status)
        )
        unhandled.append(sum(val in MERGE_UNHANDLED_NAMES for val in merge_tool_status))
        failure.append(sum(val in MERGE_FAILURE_NAMES for val in merge_tool_status))
        assert incorrect[-1] + correct[-1] + unhandled[-1] + failure[-1] == len(
            merge_tool_status
        )
        assert (
            incorrect[0] + correct[0] + unhandled[0] + failure[0]
            == incorrect[-1] + correct[-1] + unhandled[-1] + failure[-1]
        )

    # Cost plot
    fig, ax = plt.subplots()
    for idx, merge_tool in enumerate(MERGE_TOOL):
        results = []
        for cost_factor in np.linspace(1, 20, 1000):
            score = unhandled[idx] * 1 + incorrect[idx] * cost_factor
            score = score / (
                cost_factor * (unhandled[idx] + incorrect[idx] + correct[idx])
            )
            score = 1 - score
            results.append(score)
        line_style = [":", "--", "-."][idx % 3]
        ax.plot(
            np.linspace(1, 20, 1000), results, label=merge_tool, linestyle=line_style
        )
    plt.xlabel("Incorrect merges cost factor")
    plt.legend()
    plt.savefig(os.path.join(output_path, "plots", "cost.pgf"))
    plt.savefig(os.path.join(output_path, "plots", "cost.pdf"))
    plt.close()

    # Table 1 (overall results)
    table = """% Do not edit.  This file is automatically generated.
\\begin{tabular}{c|c c|c c|c c}
            Tool & 
            \\multicolumn{2}{|c|}{Correct Merges} & 
            \\multicolumn{2}{|c|}{Unhandled Merges} &
            \\multicolumn{2}{|c}{Incorrect Merges}\\\\
            \\hline
            & \\# & \\% & \\# & \\% & \\# & \\%\\\\ \n"""
    total = len(result_df)
    for merge_tool_idx, merge_tool in enumerate(MERGE_TOOL):
        correct_percentage = 100 * correct[merge_tool_idx] / total if total != 0 else 0
        unhandled_percentage = (
            100 * unhandled[merge_tool_idx] / total if total != 0 else 0
        )
        incorrect_percentage = (
            100 * incorrect[merge_tool_idx] / total if total != 0 else 0
        )
        table += f"{merge_tool.capitalize()}"
        table += f" & {correct[merge_tool_idx]} & {correct_percentage:.2f}\\%"
        table += f" & {unhandled[merge_tool_idx]} & {unhandled_percentage:.2f}\\%"
        table += f" & {incorrect[merge_tool_idx]} & {incorrect_percentage:.2f}\\%\\\\\n"
    table += "\\end{tabular}\n"

    with open(os.path.join(tables_output_path, "table_summary.tex"), "w") as file:
        file.write(table)

    # Printed Table

    my_table = PrettyTable()
    my_table.field_names = [
        "Merge Tool",
        "Correct Merges",
        "Incorrect Merges",
        "Unhandled Merges",
    ]
    for merge_tool_idx, merge_tool in enumerate(MERGE_TOOL):
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
        raise Exception("No merges found in the results file at: " + args.input_csv)

    # Table 2 (by merge source)
    table2 = """% Do not edit.  This file is automatically generated.
\\begin{tabular}{c|c c c c|c c c c|c c c c}
            Tool & 
            \\multicolumn{4}{|c|}{Correct Merges} & 
            \\multicolumn{4}{|c|}{Unhandled Merges} &
            \\multicolumn{4}{|c|}{Incorrect Merges} \\\\
            &
            \\multicolumn{2}{|c}{Main Branch} & 
            \\multicolumn{2}{c|}{Feature Branch} &
            \\multicolumn{2}{|c}{Main Branch} & 
            \\multicolumn{2}{c|}{Feature Branch} &
            \\multicolumn{2}{|c}{Main Branch} & 
            \\multicolumn{2}{c|}{Feature Branch} \\\\
            \\hline
            & \\# & \\% & \\# & \\% & \\# & \\% & \\# & \\% & \\# & \\% & \\# & \\%\\\\ \n"""

    main = result_df[result_df["branch_name"].isin(main_branch_names)]
    feature = result_df[~result_df["branch_name"].isin(main_branch_names)]

    args = []
    for merge_tool_idx, merge_tool in enumerate(MERGE_TOOL):
        mergem = main[merge_tool]
        mergef = feature[merge_tool]

        correct_main = sum(val == MERGE_STATE.Tests_passed.name for val in mergem)
        correct_main_percentage = (
            100 * correct_main / len(main) if len(main) != 0 else 0
        )
        correct_feature = sum(val == MERGE_STATE.Tests_passed.name for val in mergef)
        correct_feature_percentage = (
            100 * correct_feature / len(feature) if len(feature) > 0 else -1
        )

        incorrect_main = sum(val == MERGE_STATE.Tests_failed.name for val in mergem)
        incorrect_main_percentage = (
            100 * incorrect_main / len(main) if len(main) != 0 else 0
        )
        incorrect_feature = sum(val == MERGE_STATE.Tests_failed.name for val in mergef)
        incorrect_feature_percentage = (
            100 * incorrect_feature / len(feature) if len(feature) > 0 else -1
        )

        unhandled_main = sum(val in MERGE_UNHANDLED_NAMES for val in mergem)
        unhandled_main_percentage = (
            100 * unhandled_main / len(main) if len(main) != 0 else 0
        )
        unhandled_feature = sum(val in MERGE_UNHANDLED_NAMES for val in mergef)
        unhandled_feature_percentage = (
            100 * unhandled_feature / len(feature) if len(feature) > 0 else -1
        )

        table2 += f"            {merge_tool.capitalize()}"
        table2 += f" & {correct_main} & {correct_main_percentage:0.2f}\\%"
        table2 += f" & {correct_feature} & {correct_feature_percentage:0.2f}\\%"
        table2 += f" & {unhandled_main} & {unhandled_main_percentage:0.2f}\\%"
        table2 += f" & {unhandled_feature} & {unhandled_feature_percentage:0.2f}\\%"
        table2 += f" & {incorrect_main} & {incorrect_main_percentage:0.2f}\\%"
        table2 += (
            f" & {incorrect_feature} & {incorrect_feature_percentage:0.2f}\\%\\\\ \n"
        )

    table2 += "\\end{tabular}\n"

    with open(
        os.path.join(tables_output_path, "table_feature_main_summary.tex"), "w"
    ) as file:
        file.write(table2)

    # Table 3 (Run-time)
    table3 = """% Do not edit.  This file is automatically generated.
\\begin{tabular}{c|c|c|c}
    Tool & Mean Run-time & Median Run-time & Max Run-time\\\\
    \\hline\n"""

    args = []
    for merge_tool in MERGE_TOOL:
        table3 += f"    {merge_tool.capitalize()}"
        for f in [np.mean, np.median, np.max]:
            run_time = f(result_df[merge_tool + " run_time"])
            table3 += f" & {run_time:0.2f}"
        table3 += "\\\\\n"
    table3 += "\\end{tabular}\n"

    with open(os.path.join(tables_output_path, "table_run_time.tex"), "w") as file:
        file.write(table3)
