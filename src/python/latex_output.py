#!/usr/bin/env python3
"""Output LaTeX tables and plots.

usage: python3 latex_output.py
                --full_repos_csv <path_to_full_repos_csv>
                --valid_repos_csv <path_to_valid_repos_csv>
                --n_merges <number_of_merges>
                --result_csv <path_to_result_csv>
                --merges_path <path_to_merges>
                --merges_valid_path <path_to_merges_valid>
                --output_dir <path_to_output>


The script generates all the tables and plots for the paper. It requires the
following input files:
- full_repos_csv: csv file containing the full list of repositories
- valid_repos_csv: csv file containing the list of valid repositories
- result_csv: csv file containing the merge results
- merges_path: path to the folder containing the merge results
- merges_valid_path: path to the folder containing the merge results for valid repositories
- output_dir: path to the folder where the output files will be saved
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

from merge_tester import MERGE_TOOL, TIMEOUT_TESTING_MERGE, TIMEOUT_TESTING_PARENT
from merge_filter import TIMEOUT_MERGING
from repo import MERGE_STATE, TEST_STATE

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
    "spork": "Spork",
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
    return name.capitalize()


def filter_outliers_IQR(df):
    """Filter outliers using IQR
    Args:
         df: dataframe containing the data
     Returns:
         dataframe without outliers
    """
    df = df[df >= 0]
    q1 = df.quantile(0.25)
    q3 = df.quantile(0.75)
    IQR = q3 - q1
    outliers_mask = (df < (q1 - 1.5 * IQR)) | (df > (q3 + 1.5 * IQR))
    print(f"Number of outliers {df.name}: {outliers_mask.sum()}")
    result = df[~outliers_mask]
    return result


def add_def(name, value) -> str:
    """Add a LaTeX definition.
    Args:
        name: name of the definition
        value: value of the definition
    Returns:
        LaTeX definition
    """
    return "\\def\\" + name + "{" + str(value) + "\\xspace}\n"


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
    TEST_STATE.Tests_running.name,
    MERGE_STATE.Git_checkout_failed.name,
    MERGE_STATE.Merge_timedout.name,
]


main_branch_names = ["main", "refs/heads/main", "master", "refs/heads/master"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full_repos_csv", type=str, default="input_data/repos_with_hashes.csv"
    )
    parser.add_argument(
        "--valid_repos_csv", type=str, default="results/valid_repos.csv"
    )
    parser.add_argument(
        "--tested_merges_path", type=str, default="results/merges_tested"
    )
    parser.add_argument("--n_merges", type=int, default=20)
    parser.add_argument("--result_csv", type=str, default="results/result.csv")
    parser.add_argument("--all_merges_path", type=str, default="results/merges")
    parser.add_argument("--merges_valid_path", type=str, default="results/merges_valid")
    parser.add_argument("--output_dir", type=str, default="results")
    args = parser.parse_args()
    output_dir = args.output_dir

    # Combine results file
    result_df = []
    repos = pd.read_csv(args.valid_repos_csv, index_col="idx")
    for _, repository_data in tqdm(repos.iterrows(), total=len(repos)):
        merges_repo = []
        repo_name = repository_data["repository"]
        merge_list_file = Path(
            os.path.join(args.tested_merges_path, repo_name.split("/")[1] + ".csv")
        )
        if not merge_list_file.exists():
            raise Exception(
                "merge_filter: Skipping",
                repo_name,
                "because it does not have a list of merge. Missing file: ",
                merge_list_file,
            )

        try:
            merges = pd.read_csv(merge_list_file, header=0, index_col="idx")
        except pd.errors.EmptyDataError:
            print("merge_tester: Skipping", repo_name, "because it is empty.")
            continue
        merges = merges[merges["parent pass"]]
        merges["repo_name"] = repo_name
        merges["repo-idx"] = repository_data.name
        merges["merge-idx"] = merges.index
        result_df.append(merges)

    result_df = pd.concat(result_df, ignore_index=True)
    result_df.sort_values(by=["repo-idx", "merge-idx"], inplace=True)
    result_df = result_df[
        ["repo-idx", "merge-idx"] + [col for col in result_df.columns if col != "repo-idx" and col != "merge-idx"]
    ]

    # Check if undesirable states are present
    for merge_tool in MERGE_TOOL:
        assert result_df[merge_tool.name].isin(UNDESIRABLE_STATES).sum() == 0


    result_df.to_csv(os.path.join(args.output_dir, "result.csv"), index_label="idx")

    for plot_category, merge_tools in PLOTS.items():
        plots_output_path = os.path.join(output_dir, "plots", plot_category)
        tables_output_path = os.path.join(output_dir, "tables", plot_category)
        Path(plots_output_path).mkdir(parents=True, exist_ok=True)
        Path(tables_output_path).mkdir(parents=True, exist_ok=True)

        # Figure (Heat Map diffing)
        result = np.zeros((len(merge_tools), len(merge_tools)))
        for _, row in tqdm(result_df.iterrows(), total=len(result_df)):
            for idx, merge_tool1 in enumerate(merge_tools):
                for idx2, merge_tool2 in enumerate(merge_tools[(idx + 1) :]):
                    if (
                        row[merge_tool1 + "_merge_fingerprint"]
                        != row[merge_tool2 + "_merge_fingerprint"]
                    ):
                        result[idx][idx2 + idx + 1] += 1
                        result[idx2 + idx + 1][idx] += 1
        fig, ax = plt.subplots()
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

        # Cost plot 1
        MAX_COST = 120
        fig, ax = plt.subplots()
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
        plt.ylabel("\mbox{Merge\_Score}")
        plt.xlim(0, 20)
        plt.ylim(0.75, 0.95)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(plots_output_path, "cost_without_manual.pgf"))
        plt.savefig(os.path.join(plots_output_path, "cost_without_manual.pdf"))

        # Plot with manual merges
        line = ax.plot(
            np.linspace(1, MAX_COST, 1000),
            np.zeros(1000),
            label="Manual Merging",
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
                    merge_tool_latex_name(merge_tool),
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

        main = result_df[result_df["branch_name"].isin(main_branch_names)]
        feature = result_df[~result_df["branch_name"].isin(main_branch_names)]

        for merge_tool_idx, merge_tool in enumerate(merge_tools):
            mergem = main[merge_tool]
            mergef = feature[merge_tool]

            correct_main = sum(val in MERGE_CORRECT_NAMES for val in mergem)
            correct_main_percentage = (
                100 * correct_main / len(main) if len(main) != 0 else 0
            )
            correct_feature = sum(val in MERGE_CORRECT_NAMES for val in mergef)
            correct_feature_percentage = (
                100 * correct_feature / len(feature) if len(feature) > 0 else -1
            )

            incorrect_main = sum(val in MERGE_INCORRECT_NAMES for val in mergem)
            incorrect_main_percentage = (
                100 * incorrect_main / len(main) if len(main) != 0 else 0
            )
            incorrect_feature = sum(val in MERGE_INCORRECT_NAMES for val in mergef)
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
            table3 += f"    {merge_tool.capitalize():32}"
            filtered_runtime = filter_outliers_IQR(result_df[merge_tool + "_run_time"])
            for f in [np.mean, np.median, np.max]:
                run_time = f(filtered_runtime)
                if run_time < 10:
                    table3 += f" & {run_time:0.2f}"
                elif run_time < 100:
                    table3 += f" & {run_time:0.1f}"
                else:
                    table3 += f" & {round(run_time)}"
            table3 += " \\\\\n"
        table3 += "\\end{tabular}\n"

        with open(os.path.join(tables_output_path, "table_run_time.tex"), "w") as file:
            file.write(table3)

    # Create defs.tex
    full_repos_df = pd.read_csv(args.full_repos_csv)
    valid_repos_df = pd.read_csv(args.valid_repos_csv)

    output = "% Dataset and sample numbers\n"
    output = add_def("reposInitial", len(full_repos_df))
    output += add_def("reposValid", len(valid_repos_df))

    count = 0
    for i in tqdm(os.listdir(args.all_merges_path)):
        if i.endswith(".csv"):
            df = pd.read_csv(
                os.path.join(args.all_merges_path, i),
                names=["idx", "branch_name", "merge", "left", "right", "notes"],
                header=0,
                index_col="idx",
            )
            count += len(df)
    output += add_def("mergesInitial", count)
    output += add_def("mergesPer", args.n_merges)

    repos = 0
    count = 0
    full = 0
    df = pd.read_csv(args.valid_repos_csv, index_col="idx")
    for _, repository_data in tqdm(df.iterrows(), total=len(df)):
        merge_list_file = os.path.join(
            args.merges_valid_path, repository_data["repository"].split("/")[1] + ".csv"
        )
        if not os.path.isfile(merge_list_file):
            continue
        merges = pd.read_csv(merge_list_file, index_col=0)
        if len(merges) > 0:
            repos += 1
        count += len(merges)
        if len(merges) == args.n_merges:
            full += 1

    output += add_def("reposSampled", repos)
    output += add_def("mergesSampled", count)
    output += add_def("reposYieldedFull", full)
    output += (
        "% reposTotal/mergesTotal excludes any filtered out merges - we "
        "currently filter out some inconsistent merges\n"
    )
    output += add_def("reposTotal", len(result_df["repo_name"].unique()))
    output += add_def("mergesTotal", len(result_df))

    output += "\n% Results\n"

    spork_correct = len(result_df[result_df["spork"].isin(MERGE_CORRECT_NAMES)])
    ort_correct = len(result_df[result_df["gitmerge_ort"].isin(MERGE_CORRECT_NAMES)])
    output += add_def("sporkOverOrtCorrect", spork_correct - ort_correct)

    spork_incorrect = len(result_df[result_df["spork"].isin(MERGE_INCORRECT_NAMES)])
    ort_incorrect = len(
        result_df[result_df["gitmerge_ort"].isin(MERGE_INCORRECT_NAMES)]
    )
    output += add_def("sporkOverOrtIncorrect", spork_incorrect - ort_incorrect)

    output += add_def("mainBranchMerges", len(main))
    output += add_def(
        "mainBranchMergesPercent", round(len(main) * 100 / len(result_df))
    )
    output += add_def("featureBranchMerges", len(feature))
    output += add_def(
        "featureBranchMergesPercent", round(len(feature) * 100 / len(result_df))
    )

    output += "\n% Timeout\n"
    output += add_def("parentTestTimeout", str(TIMEOUT_TESTING_PARENT // 60))
    output += add_def("mergeTestTimeout", str(TIMEOUT_TESTING_MERGE // 60))

    with open(os.path.join(args.output_dir, "defs.tex"), "w") as file:
        file.write(output)
