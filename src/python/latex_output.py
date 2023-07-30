#!/usr/bin/env python3
"""Output LaTeX tables and plots.

usage: python3 latex_output.py 
                --full_repos_csv <path_to_full_repos_csv>
                --valid_repos_csv <path_to_valid_repos_csv>
                --n_merges <number_of_merges> 
                --result_csv <path_to_result_csv>
                --merges_path <path_to_merges>
                --merges_valid_path <path_to_merges_valid>
                --output_path <path_to_output>


The script generates all the tables and plots for the paper. It requires the
following input files:
- full_repos_csv: csv file containing the full list of repositories
- valid_repos_csv: csv file containing the list of valid repositories
- result_csv: csv file containing the merge results
- merges_path: path to the folder containing the merge results
- merges_valid_path: path to the folder containing the merge results for valid repositories
- output_path: path to the folder where the output files will be saved
"""


import os
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import pandas as pd
from prettytable import PrettyTable
from parent_merges_test import TIMEOUT_TESTING
from merge_tester import TIMEOUT_TESTING as TIMEOUT_TESTING_MERGE
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


def add_def(name, value) -> str:
    """Add a LaTeX definition.
    Args:
        name: name of the definition
        value: value of the definition
    Returns:
        LaTeX definition
    """
    return "\\def\\" + name + "{" + str(value) + " }\n"


PLOTS = {
    "all": MERGE_TOOL,
    "git": [merge_tool for merge_tool in MERGE_TOOL if "git" in merge_tool],
    "tools": ["gitmerge-ort", "gitmerge-ort-ignorespace", "spork", "intellimerge"],
}

MERGE_FAILURE_NAMES = [
    MERGE_STATE.Tests_exception.name,
    MERGE_STATE.Tests_timedout.name,
]

MERGE_UNHANDLED_NAMES = [
    MERGE_STATE.Merge_failed.name,
    MERGE_STATE.Merge_exception.name,
    MERGE_STATE.Merge_timedout.name,
]
DELETE_FAILED_TRIVIAL_MERGES = True


def compute_trivial_merges(df: pd.DataFrame):
    """Compute trivial merges. A trivial merge is a merge where the base branch
    is the same as the left or right branch.
    Args:
        df: dataframe containing the merge results
    """
    trivial_merges = []
    count = 0
    for _, row in tqdm(df.iterrows(), total=len(df)):
        if row["left"] == row["base"] or row["right"] == row["base"]:
            trivial_merges.append(row)
            for merge_tool in MERGE_TOOL:
                if row[merge_tool] == MERGE_STATE.Tests_failed.name:
                    cache_merge_status_prefix = os.path.join(
                        "cache",
                        "merge_test_results",
                        "_".join(
                            [
                                row["repo_name"].split("/")[1],
                                row["left"],
                                row["right"],
                                row["base"],
                                row["merge"],
                                "",
                            ]
                        ),
                    )
                    cache_merges_status = (
                        cache_merge_status_prefix + merge_tool + ".txt"
                    )
                    count += 1
                    if DELETE_FAILED_TRIVIAL_MERGES and os.path.exists(
                        cache_merges_status
                    ):
                        os.remove(cache_merges_status)
                    else:
                        break
    print("Number of failed trivial merges:", count)
    return trivial_merges


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full_repos_csv", type=str, default="input_data/repos_small_with_hashes.csv"
    )
    parser.add_argument(
        "--valid_repos_csv", type=str, default="results/valid_repos.csv"
    )
    parser.add_argument("--n_merges", type=int, default=20)
    parser.add_argument("--result_csv", type=str, default="results/result.csv")
    parser.add_argument("--merges_path", type=str, default="results/merges")
    parser.add_argument("--merges_valid_path", type=str, default="results/merges_valid")
    parser.add_argument("--output_path", type=str, default="results")
    args = parser.parse_args()
    output_path = args.output_path

    # open results file
    result_df = pd.read_csv(args.result_csv, index_col="idx")
    old_len = len(result_df)
    inconsistent_merge_results = compute_inconsistent_merge_results(result_df)
    print(
        "Number of inconsistent entries that will be ignored:",
        len(inconsistent_merge_results),
    )
    for row in tqdm(inconsistent_merge_results):
        result_df.drop(row.name, inplace=True)
    assert old_len - len(result_df) == len(inconsistent_merge_results)

    trivial_merges = compute_trivial_merges(result_df)
    print("Number of trivial merges:", len(trivial_merges))

    result_df.to_csv(os.path.join(args.output_path, "filtered_result.csv"))

    for plot_category, merge_tools in PLOTS.items():
        plots_output_path = os.path.join(output_path, "plots", plot_category)
        tables_output_path = os.path.join(output_path, "tables", plot_category)
        Path(plots_output_path).mkdir(parents=True, exist_ok=True)
        Path(tables_output_path).mkdir(parents=True, exist_ok=True)
        # Figure (Heat Map diffing)
        result = np.zeros((len(merge_tools), len(merge_tools)))
        for _, row in tqdm(result_df.iterrows(), total=len(result_df)):
            for idx, merge_tool1 in enumerate(merge_tools):
                for idx2, merge_tool2 in enumerate(merge_tools[(idx + 1) :]):
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
        latex_merge_tool = ["$" + i.capitalize() + "$" for i in merge_tools]
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
        heatmap.set_xticklabels(
            labels=heatmap.get_xticklabels(),
            rotation=45,
            ha="right",
            rotation_mode="anchor",
        )
        plt.tight_layout()
        plt.savefig(os.path.join(plots_output_path, "heatmap.pgf"))
        plt.savefig(os.path.join(plots_output_path, "heatmap.pdf"))
        plt.close()
        # Correct the path to the stored image in the pgf file.
        with open(os.path.join(plots_output_path, "heatmap.pgf"), "rt") as f:
            file_content = f.read()
        file_content = file_content.replace(
            "heatmap-img0.png", f"plots/{plot_category}/heatmap-img0.png"
        )
        with open(os.path.join(plots_output_path, "heatmap.pgf"), "wt") as f:
            f.write(file_content)

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
            unhandled.append(
                sum(val in MERGE_UNHANDLED_NAMES for val in merge_tool_status)
            )
            failure.append(sum(val in MERGE_FAILURE_NAMES for val in merge_tool_status))
            assert incorrect[-1] + correct[-1] + unhandled[-1] + failure[-1] == len(
                merge_tool_status
            )
            assert (
                incorrect[0] + correct[0] + unhandled[0] + failure[0]
                == incorrect[-1] + correct[-1] + unhandled[-1] + failure[-1]
            )

        # Cost plot 1
        MAX_COST = 95
        fig, ax = plt.subplots()
        for idx, merge_tool in enumerate(MERGE_TOOL):
            results = []
            for cost_factor in np.linspace(1, MAX_COST, 1000):
                score = unhandled[idx] * 1 + incorrect[idx] * cost_factor
                score = score / ((unhandled[idx] + incorrect[idx] + correct[idx]))
                score = 1 - score
                results.append(score)
            line_style = [":", "--", "-."][idx % 3]
            ax.plot(
                np.linspace(1, MAX_COST, 1000),
                results,
                label=merge_tool,
                linestyle=line_style,
            )
        plt.xlabel("Incorrect merges cost factor")
        plt.ylabel("$Merge\_Score$")
        plt.xlim(0, 20)
        plt.ylim(0.65, 0.95)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(plots_output_path, "cost_without_manual.pgf"))
        plt.savefig(os.path.join(plots_output_path, "cost_without_manual.pdf"))

        # Plot with manual merges
        line = ax.plot(
            np.linspace(1, MAX_COST, 1000),
            np.zeros(1000),
            label="Manual Merges",
            color="red",
        )
        plt.xlim(0, MAX_COST)
        plt.ylim(-0.1, 1.0)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(plots_output_path, "cost_with_manual.pgf"))
        plt.savefig(os.path.join(plots_output_path, "cost_with_manual.pdf"))
        plt.close()

        # Table 1 (overall results)
        table = """% Do not edit.  This file is automatically generated.
\\begin{tabular}{c|c c|c c|c c}
            Tool & 
            \\multicolumn{2}{|c|}{Correct Merges} & 
            \\multicolumn{2}{|c|}{Unhandled Merges} &
            \\multicolumn{2}{|c}{Incorrect Merges} \\\\
            & \\# & \\% & \\# & \\% & \\# & \\% \\\\
            \\hline\n"""
        total = len(result_df)
        for merge_tool_idx, merge_tool in enumerate(merge_tools):
            correct_percentage = (
                100 * correct[merge_tool_idx] / total if total != 0 else 0
            )
            unhandled_percentage = (
                100 * unhandled[merge_tool_idx] / total if total != 0 else 0
            )
            incorrect_percentage = (
                100 * incorrect[merge_tool_idx] / total if total != 0 else 0
            )
            table += f"{merge_tool.capitalize():30}"
            table += (
                f" & {correct[merge_tool_idx]:5} & {round(correct_percentage):3}\\%"
            )
            table += (
                f" & {unhandled[merge_tool_idx]:5} & {round(unhandled_percentage):3}\\%"
            )
            table += f" & {incorrect[merge_tool_idx]:5} & {round(incorrect_percentage):3}\\% \\\\\n"
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
        for merge_tool_idx, merge_tool in enumerate(merge_tools):
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
            raise Exception(
                "No merges found in the results file at: " + args.result_csv
            )

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
            & \\# & \\% & \\# & \\% & \\# & \\% & \\# & \\% & \\# & \\% & \\# & \\% \\\\ \n"""

        main = result_df[result_df["branch_name"].isin(main_branch_names)]
        feature = result_df[~result_df["branch_name"].isin(main_branch_names)]

        for merge_tool_idx, merge_tool in enumerate(merge_tools):
            mergem = main[merge_tool]
            mergef = feature[merge_tool]

            correct_main = sum(val == MERGE_STATE.Tests_passed.name for val in mergem)
            correct_main_percentage = (
                100 * correct_main / len(main) if len(main) != 0 else 0
            )
            correct_feature = sum(
                val == MERGE_STATE.Tests_passed.name for val in mergef
            )
            correct_feature_percentage = (
                100 * correct_feature / len(feature) if len(feature) > 0 else -1
            )

            incorrect_main = sum(val == MERGE_STATE.Tests_failed.name for val in mergem)
            incorrect_main_percentage = (
                100 * incorrect_main / len(main) if len(main) != 0 else 0
            )
            incorrect_feature = sum(
                val == MERGE_STATE.Tests_failed.name for val in mergef
            )
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

            table2 += f"            {merge_tool.capitalize():30}"
            table2 += f" & {correct_main:5} & {round(correct_main_percentage):3}\\%"
            table2 += (
                f" & {correct_feature:5} & {round(correct_feature_percentage):3}\\%"
            )
            table2 += f" & {unhandled_main:5} & {round(unhandled_main_percentage):3}\\%"
            table2 += (
                f" & {unhandled_feature:5} & {round(unhandled_feature_percentage):3}\\%"
            )
            table2 += f" & {incorrect_main:5} & {round(incorrect_main_percentage):3}\\%"
            table2 += (
                f" & {incorrect_feature:5}"
                + f" & {round(incorrect_feature_percentage):3}\\% \\\\ \n"
            )

        table2 += "\\end{tabular}\n"

        with open(
            os.path.join(tables_output_path, "table_feature_main_summary.tex"), "w"
        ) as file:
            file.write(table2)

        # Table 3 (Run-time)
        table3 = """% Do not edit.  This file is automatically generated.
\\begin{tabular}{c|c|c|c}
    & \multicolumn{3}{c}{Run time (seconds)} \\\\
    Tool & Mean & Median & Max \\\\
    \\hline\n"""

        for merge_tool in merge_tools:
            table3 += f"    {merge_tool.capitalize():30}"
            for f in [np.mean, np.median, np.max]:
                run_time = f(result_df[merge_tool + " run_time"])
                table3 += f" & {round(run_time):5}"
            table3 += " \\\\\n"
        table3 += "\\end{tabular}\n"

        with open(os.path.join(tables_output_path, "table_run_time.tex"), "w") as file:
            file.write(table3)

    # Create defs.tex
    df = pd.read_csv(args.full_repos_csv)
    output = add_def("reposInitial", len(df))
    output += add_def("parentTestTimeout", str(TIMEOUT_TESTING // 60))
    output += add_def("mergeTestTimeout", str(TIMEOUT_TESTING_MERGE // 60))
    df = pd.read_csv(args.valid_repos_csv)
    output += add_def("reposValid", len(df))
    output += add_def("mergesPer", args.n_merges)
    df = pd.read_csv(args.result_csv)
    output += add_def("mergesTrivial", len(trivial_merges))

    count = 0
    for i in tqdm(os.listdir(args.merges_path)):
        if i.endswith(".csv"):
            df = pd.read_csv(
                os.path.join(args.merges_path, i),
                names=["branch_name", "merge", "left", "right", "base"],
                header=0,
            )
            count += len(df)
    output += add_def("mergesInitial", count)

    count = 0
    for i in tqdm(os.listdir(args.merges_valid_path)):
        if i.endswith(".csv"):
            df = pd.read_csv(os.path.join(args.merges_valid_path, i), index_col="idx")
            count += len(df)
    output += add_def("mergesSampled", count)

    with open(os.path.join(args.output_path, "defs.tex"), "w") as file:
        file.write(output)
