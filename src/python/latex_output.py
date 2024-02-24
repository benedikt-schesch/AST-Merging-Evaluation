#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Output LaTeX tables and plots.

usage: python3 latex_output.py
                --full_repos_csv <path_to_full_repos_csv>
                --repos_head_passes_csv <path_to_repos_head_passes_csv>
                --n_merges <number_of_merges>
                --tested_merges_path <path_to_tested_merges>
                --merges_path <path_to_merges>
                --output_dir <path_to_output>


This script generates all the tables and plots for the paper. It requires the
following input files:
- full_repos_csv: csv file containing the full list of repositories
- repos_head_passes_csv: csv file containing the list of repositories whose head passes tests
- tested_merges_path: path to the directory containing the merge results
- merges_path: path to the directory containing all found merges.
- output_dir: path to the directory where the LaTeX files will be saved
"""


import os
import argparse
from pathlib import Path
import warnings

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import pandas as pd
from prettytable import PrettyTable
from tqdm import tqdm
import seaborn as sns

from variables import TIMEOUT_TESTING_PARENT, TIMEOUT_TESTING_MERGE
from repo import MERGE_STATE, TEST_STATE, MERGE_TOOL

matplotlib.use("pgf")
matplotlib.rcParams.update(
    {
        "pgf.texsystem": "pdflatex",
        "font.family": "serif",
        "text.usetex": True,
        "pgf.rcfonts": False,
    }
)

MERGE_TOOL_RENAME = {
    "intellimerge": "IntelliMerge",
}


def merge_tool_latex_name(name: str) -> str:
    """Return the LaTeX name of a merge tool.
    Args:
        name: name of the merge tool
    Returns:
        LaTeX name of the merge tool
    """
    if name in MERGE_TOOL_RENAME:
        return MERGE_TOOL_RENAME[name]
    name = name.capitalize()
    name = name.replace("_", "-")
    return name.capitalize()


def latex_def(name, value) -> str:
    """Return a LaTeX definition.
    Args:
        name: name of the definition
        value: value of the definition
    Returns:
        LaTeX definition
    """
    return "\\def\\" + name + "{" + str(value) + "\\xspace}\n"


# Dictonary that lists the different subsets of merge tools for which plots
# and tables are generated. The key is the directory name which will contain all figures
# that will be used and the value is the list of plots to contain.
PLOTS = {
    "all": [merge_tool.name for merge_tool in MERGE_TOOL],
    "git": [
        merge_tool.name for merge_tool in MERGE_TOOL if "gitmerge" in merge_tool.name
    ],
    "tools": [
        "gitmerge_ort",
        "gitmerge_ort_ignorespace",
        "git_hires_merge",
        "spork",
        "intellimerge",
    ],
}

MERGE_CORRECT_NAMES = [
    TEST_STATE.Tests_passed.name,
]

MERGE_INCORRECT_NAMES = [
    TEST_STATE.Tests_failed.name,
    TEST_STATE.Tests_timedout.name,
]

MERGE_UNHANDLED_NAMES = [
    MERGE_STATE.Merge_failed.name,
    MERGE_STATE.Merge_timedout.name,
]

UNDESIRABLE_STATES = [
    TEST_STATE.Git_checkout_failed.name,
    TEST_STATE.Not_tested.name,
    MERGE_STATE.Git_checkout_failed.name,
    MERGE_STATE.Merge_timedout.name,
]


main_branch_names = ["main", "refs/heads/main", "master", "refs/heads/master"]


def main():  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """Main function"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_name", type=str)
    parser.add_argument("--full_repos_csv", type=Path)
    parser.add_argument("--repos_head_passes_csv", type=Path)
    parser.add_argument("--tested_merges_path", type=Path)
    parser.add_argument("--merges_path", type=Path)
    parser.add_argument("--analyzed_merges_path", type=Path)
    parser.add_argument("--n_merges", type=int, default=20)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--timed_merges_path", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir

    # Combine results file
    result_df_list = []
    repos = pd.read_csv(args.repos_head_passes_csv, index_col="idx")
    for _, repository_data in tqdm(repos.iterrows(), total=len(repos)):
        repo_slug = repository_data["repository"]
        merge_list_file = args.tested_merges_path / (repo_slug + ".csv")
        if not merge_list_file.exists():
            raise Exception(
                "latex_ouput.py:",
                repo_slug,
                "does not have a list of merges. Missing file: ",
                merge_list_file,
            )

        try:
            merges = pd.read_csv(merge_list_file, header=0, index_col="idx")
            if len(merges) == 0:
                raise pd.errors.EmptyDataError
        except pd.errors.EmptyDataError:
            print(
                "latex_output: Skipping",
                repo_slug,
                "because it does not contain any merges.",
            )
            continue
        merges = merges[merges["parents pass"]]
        if len(merges) > args.n_merges:
            merges = merges.sample(args.n_merges, random_state=42)
            merges.sort_index(inplace=True)
        merges["repository"] = repo_slug
        merges["repo-idx"] = repository_data.name
        merges["merge-idx"] = merges.index
        result_df_list.append(merges)

    result_df = pd.concat(result_df_list, ignore_index=True)
    result_df.sort_values(by=["repo-idx", "merge-idx"], inplace=True)
    result_df = result_df[
        ["repo-idx", "merge-idx"]
        + [col for col in result_df.columns if col not in ("repo-idx", "merge-idx")]
    ]

    # Remove undesired states
    for merge_tool in MERGE_TOOL:
        result_df = result_df[~result_df[merge_tool.name].isin(UNDESIRABLE_STATES)]

    result_df.to_csv(args.output_dir / "result.csv", index_label="idx")

    main = result_df[result_df["branch_name"].isin(main_branch_names)]
    feature = result_df[~result_df["branch_name"].isin(main_branch_names)]

    for plot_category, merge_tools in PLOTS.items():
        plots_output_path = output_dir / "plots" / plot_category
        tables_output_path = output_dir / "tables" / plot_category
        Path(plots_output_path).mkdir(parents=True, exist_ok=True)
        Path(tables_output_path).mkdir(parents=True, exist_ok=True)

        # Figure Heat map diffing
        result = np.zeros((len(merge_tools), len(merge_tools)))
        for _, row in tqdm(result_df.iterrows(), total=len(result_df)):
            for idx, merge_tool1 in enumerate(merge_tools):
                for idx2, merge_tool2 in enumerate(merge_tools[(idx + 1) :]):
                    if row[merge_tool1 + "_merge_fingerprint"] != row[
                        merge_tool2 + "_merge_fingerprint"
                    ] and (
                        row[merge_tool1] in MERGE_CORRECT_NAMES
                        or row[merge_tool2] in MERGE_CORRECT_NAMES
                    ):
                        result[idx][idx2 + idx + 1] += 1
                        result[idx2 + idx + 1][idx] += 1
        _, ax = plt.subplots(figsize=(8, 6))
        result = np.tril(result)
        latex_merge_tool = [
            "\\mbox{" + merge_tool_latex_name(i) + "}" for i in merge_tools
        ]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            heatmap = sns.heatmap(
                result,
                annot=True,
                ax=ax,
                xticklabels=latex_merge_tool,  # type: ignore
                yticklabels=latex_merge_tool,  # type: ignore
                fmt="g",
                mask=np.triu(np.ones_like(result, dtype=bool), k=1),
                cmap="Blues",
                annot_kws={"size": 6},
            )
        heatmap.set_yticklabels(labels=heatmap.get_yticklabels(), va="center")
        heatmap.set_xticklabels(
            labels=heatmap.get_xticklabels(),
            rotation=45,
            ha="right",
            rotation_mode="anchor",
        )
        plt.tight_layout()
        plt.savefig(plots_output_path / "heatmap.pgf")
        plt.savefig(plots_output_path / "heatmap.pdf")
        plt.close()
        # Correct the path to the stored image in the pgf file.
        with open(plots_output_path / "heatmap.pgf", "rt", encoding="utf-8") as f:
            file_content = f.read()
        file_content = file_content.replace(
            "heatmap-img0.png", f"plots/{plot_category}/heatmap-img0.png"
        )
        with open(plots_output_path / "heatmap.pgf", "wt", encoding="utf-8") as f:
            f.write(file_content)

        incorrect = []
        correct = []
        unhandled = []
        for merge_tool in merge_tools:
            merge_tool_status = result_df[merge_tool]
            correct.append(sum(val in MERGE_CORRECT_NAMES for val in merge_tool_status))
            incorrect.append(
                sum(val in MERGE_INCORRECT_NAMES for val in merge_tool_status)
            )
            unhandled.append(
                sum(val in MERGE_UNHANDLED_NAMES for val in merge_tool_status)
            )
            assert incorrect[-1] + correct[-1] + unhandled[-1] == len(merge_tool_status)
            assert (
                incorrect[0] + correct[0] + unhandled[0]
                == incorrect[-1] + correct[-1] + unhandled[-1]
            )

        # Cost plot
        MAX_COST = 120
        _, ax = plt.subplots()
        for idx, merge_tool in enumerate(merge_tools):
            results = []
            for cost_factor in np.linspace(1, MAX_COST, 1000):
                score = unhandled[idx] * 1 + incorrect[idx] * cost_factor
                score = score / ((unhandled[idx] + incorrect[idx] + correct[idx]))
                score = 1 - score
                results.append(score)
            line_style = [(idx, (1, 1)), "--", "-."][idx % 3]
            ax.plot(
                np.linspace(1, MAX_COST, 1000),
                results,
                label=merge_tool_latex_name(merge_tool),
                linestyle=line_style,
                linewidth=3,
                alpha=0.8,
            )
        plt.xlabel("Incorrect merges cost factor $k$")
        plt.ylabel("\\mbox{Merge_Score}")
        plt.xlim(0, 20)
        plt.ylim(0.75, 0.95)
        plt.legend()
        plt.tight_layout()
        plt.savefig(plots_output_path / "cost_without_manual.pgf")
        plt.savefig(plots_output_path / "cost_without_manual.pdf")

        # Cost plot with manual merges
        ax.plot(
            np.linspace(1, MAX_COST, 1000),
            np.zeros(1000),
            label="Manual Merging",
            color="red",
        )
        plt.xlim(0, MAX_COST)
        plt.ylim(-0.1, 1.0)
        plt.legend()
        plt.tight_layout()
        plt.savefig(plots_output_path / "cost_with_manual.pgf")
        plt.savefig(plots_output_path / "cost_with_manual.pdf")
        plt.close()

        # Table overall results
        table = """% Do not edit.  This file is automatically generated.
\\begin{tabular}{l|c c|c c|c c}
            Tool &
            \\multicolumn{2}{c|}{Correct Merges} &
            \\multicolumn{2}{c|}{Unhandled Merges} &
            \\multicolumn{2}{c}{Incorrect Merges} \\\\
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
            table += f"{merge_tool_latex_name(merge_tool):32}"
            table += (
                f" & {correct[merge_tool_idx]:5} & {round(correct_percentage):3}\\%"
            )
            table += (
                f" & {unhandled[merge_tool_idx]:5} & {round(unhandled_percentage):3}\\%"
            )
            table += f" & {incorrect[merge_tool_idx]:5} & {round(incorrect_percentage):3}\\% \\\\\n"
        table += "\\end{tabular}\n"

        with open(
            tables_output_path / "table_summary.tex", "w", encoding="utf-8"
        ) as file:
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
                    merge_tool_latex_name(merge_tool),
                    correct[merge_tool_idx],
                    incorrect[merge_tool_idx],
                    unhandled[merge_tool_idx],
                ]
            )

        print(my_table)
        if total == 0:
            raise Exception("No merges found in the results")

        # Table by merge source
        table2 = """% Do not edit.  This file is automatically generated.
\\begin{tabular}{c|c c c c|c c c c|c c c c}
            Tool &
            \\multicolumn{4}{c|}{Correct Merges} &
            \\multicolumn{4}{c|}{Unhandled Merges} &
            \\multicolumn{4}{c}{Incorrect Merges} \\\\
            &
            \\multicolumn{2}{c}{Main Branch} &
            \\multicolumn{2}{c|}{Feature Branch} &
            \\multicolumn{2}{c}{Main Branch} &
            \\multicolumn{2}{c|}{Feature Branch} &
            \\multicolumn{2}{c}{Main Branch} &
            \\multicolumn{2}{c}{Feature Branch} \\\\
            \\hline
            & \\# & \\% & \\# & \\% & \\# & \\% & \\# & \\% & \\# & \\% & \\# & \\% \\\\\n"""

        for merge_tool_idx, merge_tool in enumerate(merge_tools):
            merge_main = main[merge_tool]
            merge_feature = feature[merge_tool]

            correct_main = sum(val in MERGE_CORRECT_NAMES for val in merge_main)
            correct_main_percentage = (
                100 * correct_main / len(main) if len(main) != 0 else 0
            )
            correct_feature = sum(val in MERGE_CORRECT_NAMES for val in merge_feature)
            correct_feature_percentage = (
                100 * correct_feature / len(feature) if len(feature) > 0 else -1
            )

            incorrect_main = sum(val in MERGE_INCORRECT_NAMES for val in merge_main)
            incorrect_main_percentage = (
                100 * incorrect_main / len(main) if len(main) != 0 else 0
            )
            incorrect_feature = sum(
                val in MERGE_INCORRECT_NAMES for val in merge_feature
            )
            incorrect_feature_percentage = (
                100 * incorrect_feature / len(feature) if len(feature) > 0 else -1
            )

            unhandled_main = sum(val in MERGE_UNHANDLED_NAMES for val in merge_main)
            unhandled_main_percentage = (
                100 * unhandled_main / len(main) if len(main) != 0 else 0
            )
            unhandled_feature = sum(
                val in MERGE_UNHANDLED_NAMES for val in merge_feature
            )
            unhandled_feature_percentage = (
                100 * unhandled_feature / len(feature) if len(feature) > 0 else -1
            )

            table2 += f"            {merge_tool_latex_name(merge_tool):32}"
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
                + f" & {round(incorrect_feature_percentage):3}\\% \\\\\n"
            )

        table2 += "\\end{tabular}\n"

        with open(
            tables_output_path / "table_feature_main_summary.tex",
            "w",
            encoding="utf-8",
        ) as file:
            file.write(table2)

            # Table run time
            if args.timed_merges_path:
                table3 = """% Do not edit.  This file is automatically generated.
    \\begin{tabular}{c|c|c|c}
        & \\multicolumn{3}{c}{Run time (seconds)} \\\\
        Tool & Mean & Median & Max \\\\
        \\hline\n"""
                timed_df = []
                for _, repository_data in tqdm(repos.iterrows(), total=len(repos)):
                    repo_slug = repository_data["repository"]
                    merges = pd.read_csv(
                        Path(args.timed_merges_path) / f"{repo_slug}.csv",
                        header=0,
                    )
                    timed_df.append(merges)
                timed_df = pd.concat(timed_df, ignore_index=True)

                for merge_tool in merge_tools:
                    table3 += f"    {merge_tool_latex_name(merge_tool):32}"
                    for f in [np.mean, np.median, np.max]:
                        run_time = f(timed_df[merge_tool + "_run_time"])
                        if run_time < 10:
                            table3 += f" & {run_time:0.2f}"
                        elif run_time < 100:
                            table3 += f" & {run_time:0.1f}"
                        else:
                            table3 += f" & {round(run_time)}"
                    table3 += " \\\\\n"
                table3 += "\\end{tabular}\n"

                with open(
                    tables_output_path / "table_run_time.tex",
                    "w",
                    encoding="utf-8",
                ) as file:
                    file.write(table3)

    # Create defs.tex
    full_repos_df = pd.read_csv(args.full_repos_csv)
    repos_head_passes_df = pd.read_csv(args.repos_head_passes_csv)

    # Change from _a to A capitalizaion
    run_name_camel_case = args.run_name.split("_")[0] + "".join(
        x.title() for x in args.run_name.split("_")[1:]
    )

    output = "% Dataset and sample numbers\n"
    output = latex_def(run_name_camel_case + "ReposInitial", len(full_repos_df))
    output += latex_def(run_name_camel_case + "ReposValid", len(repos_head_passes_df))

    count_merges_initial = 0
    # Read all files and files in subfolder of args.merges_path that end in .csv
    for csv_file in Path(args.merges_path).rglob("*.csv"):
        try:
            df = pd.read_csv(
                csv_file,
                header=0,
                index_col="idx",
            )
            count_merges_initial += len(df)
        except pd.errors.EmptyDataError:
            continue
    output += latex_def(run_name_camel_case + "MergesInitial", count_merges_initial)
    output += latex_def(run_name_camel_case + "MergesPer", args.n_merges)

    count_merges_java_diff = 0
    count_repos_merges_java_diff = 0
    count_merges_diff_and_parents_pass = 0
    count_repos_merges_diff_and_parents_pass = 0
    for csv_file in Path(args.analyzed_merges_path).rglob("*.csv"):
        try:
            df = pd.read_csv(
                csv_file,
                header=0,
                index_col="idx",
            )
            if len(df) == 0:
                continue
            count_merges_java_diff += df["diff contains java file"].dropna().sum()
            count_merges_diff_and_parents_pass += df["test merge"].dropna().sum()
            if df["diff contains java file"].dropna().sum() > 0:
                count_repos_merges_java_diff += 1
            if df["test merge"].dropna().sum() > 0:
                count_repos_merges_diff_and_parents_pass += 1
        except pd.errors.EmptyDataError:
            continue

    output += latex_def(run_name_camel_case + "MergesJavaDiff", count_merges_java_diff)
    output += latex_def(
        run_name_camel_case + "ReposJavaDiff", count_repos_merges_java_diff
    )
    output += latex_def(
        run_name_camel_case + "MergesJavaDiffAndParentsPass",
        count_merges_diff_and_parents_pass,
    )
    output += latex_def(
        run_name_camel_case + "ReposJavaDiffAndParentsPass",
        count_repos_merges_diff_and_parents_pass,
    )

    repos = 0
    count = 0
    full = 0
    df = pd.read_csv(args.repos_head_passes_csv, index_col="idx")
    for _, repository_data in tqdm(df.iterrows(), total=len(df)):
        merge_list_file = args.tested_merges_path / (
            repository_data["repository"] + ".csv"
        )
        if not os.path.isfile(merge_list_file):
            continue
        try:
            merges = pd.read_csv(merge_list_file, index_col=0)
        except pd.errors.EmptyDataError:
            continue
        if len(merges) > 0:
            repos += 1
        count += len(merges)
        if len(merges) == args.n_merges:
            full += 1

    output += latex_def(run_name_camel_case + "ReposSampled", repos)
    output += latex_def(run_name_camel_case + "MergesSampled", count)
    output += latex_def(run_name_camel_case + "ReposYieldedFull", full)
    output += latex_def(
        run_name_camel_case + "ReposTotal", len(result_df["repository"].unique())
    )
    output += latex_def(run_name_camel_case + "MergesTotal", len(result_df))

    output += "\n% Results\n"

    spork_correct = len(result_df[result_df["spork"].isin(MERGE_CORRECT_NAMES)])
    ort_correct = len(result_df[result_df["gitmerge_ort"].isin(MERGE_CORRECT_NAMES)])
    output += latex_def(
        run_name_camel_case + "SporkOverOrtCorrect", spork_correct - ort_correct
    )

    spork_incorrect = len(result_df[result_df["spork"].isin(MERGE_INCORRECT_NAMES)])
    ort_incorrect = len(
        result_df[result_df["gitmerge_ort"].isin(MERGE_INCORRECT_NAMES)]
    )
    output += latex_def(
        run_name_camel_case + "SporkOverOrtIncorrect", spork_incorrect - ort_incorrect
    )

    output += latex_def(run_name_camel_case + "MainBranchMerges", len(main))
    output += latex_def(
        run_name_camel_case + "MainBranchMergesPercent",
        round(len(main) * 100 / len(result_df)),
    )
    output += latex_def(run_name_camel_case + "FeatureBranchMerges", len(feature))
    output += latex_def(
        run_name_camel_case + "FeatureBranchMergesPercent",
        round(len(feature) * 100 / len(result_df)),
    )
    output += latex_def(
        run_name_camel_case + "ReposJava",
        len(full_repos_df),
    )

    output += "\n% Timeout\n"
    output += latex_def(
        run_name_camel_case + "ParentTestTimeout", str(TIMEOUT_TESTING_PARENT // 60)
    )
    output += latex_def(
        run_name_camel_case + "MergeTestTimeout", str(TIMEOUT_TESTING_MERGE // 60)
    )

    with open(args.output_dir / "defs.tex", "w", encoding="utf-8") as file:
        file.write(output)


if __name__ == "__main__":
    main()
