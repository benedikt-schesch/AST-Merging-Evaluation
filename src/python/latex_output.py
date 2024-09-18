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
from typing import List
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import pandas as pd
from prettytable import PrettyTable
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TextColumn,
)
import seaborn as sns

from variables import TIMEOUT_TESTING_PARENT, TIMEOUT_TESTING_MERGE
from repo import MERGE_STATE, TEST_STATE, MERGE_TOOL
from loguru import logger
from cache_utils import lookup_in_cache

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
    "gitmerge_ort_adjacent": "Adjacent+ort",
    "gitmerge_ort_imports": "Imports+ort",
    "gitmerge_ort_imports_ignorespace": "Imports+ort-ignorespace",
    "intellimerge": "IntelliMerge",
    "git_hires_merge": "Hires-Merge",
    "adjacent": "Adjacent",
    "imports": "Imports",
    "version_numbers": "Version Numbers",
    "ivn": "IVn",
    "ivn_ignorespace": "IVn-ignorespace",
}


def check_fingerprint_consistency(result_df: pd.DataFrame, merge_tools: List[str]):
    """Check if the fingerprints are consistent.

    Args:
        result_df: DataFrame containing the results of the merge tools
        merge_tools: list of merge tools
    """
    for merge_tool1 in merge_tools:
        for merge_tool2 in merge_tools:
            if merge_tool1 == "gitmerge_resolve" or merge_tool2 == "gitmerge_resolve":
                continue
            # ignore adajcent
            if (
                merge_tool1 == "gitmerge_ort_adjacent"
                or merge_tool2 == "gitmerge_ort_adjacent"
            ):
                continue
            # Ignore
            if (
                merge_tool1 == "gitmerge_ort_imports"
                or merge_tool2 == "gitmerge_ort_imports"
            ):
                continue
            if (
                merge_tool1 == "gitmerge_ort_imports_ignorespace"
                or merge_tool2 == "gitmerge_ort_imports_ignorespace"
            ):
                continue
            if merge_tool1 != merge_tool2:
                # Check if fingerprints are the same
                same_fingerprint_mask = (
                    result_df[merge_tool1 + "_merge_fingerprint"]
                    == result_df[merge_tool2 + "_merge_fingerprint"]
                )

                # Check if results are the same
                same_result_mask = result_df[merge_tool1] == result_df[merge_tool2]

                # Check if the fingerprints are the same but the results are different
                inconsistent_mask = same_fingerprint_mask & ~same_result_mask
                if inconsistent_mask.sum() > 0:
                    logger.warning(
                        f"Inconsistency found between {merge_tool1} and {merge_tool2} in {inconsistent_mask.sum()} cases."
                    )
                    logger.warning(
                        result_df.loc[inconsistent_mask][
                            [
                                merge_tool1,
                                merge_tool2,
                                merge_tool1 + "_merge_fingerprint",
                            ]
                        ]
                    )


def merge_tool_latex_name(name: str) -> str:
    """Return the LaTeX name of a merge tool.
    Args:
        name: name of the merge tool
    Returns:
        LaTeX name of the merge tool
    """
    if name in MERGE_TOOL_RENAME:
        return MERGE_TOOL_RENAME[name]
    return name.replace("_", "-").replace("plumelib", "P").capitalize()


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
        "gitmerge_ort",
        "gitmerge_ort_ignorespace",
        "gitmerge_recursive_histogram",
        "gitmerge_recursive_minimal",
        "gitmerge_recursive_myers",
        "gitmerge_recursive_patience",
        "gitmerge_resolve",
    ],
    "tools": [
        "gitmerge_ort",
        "gitmerge_ort_ignorespace",
        "git_hires_merge",
        "spork",
        "intellimerge",
        "adjacent",
        "imports",
        "version_numbers",
        "ivn",
        "ivn_ignorespace",
    ],
}

MERGE_CORRECT_NAMES = [
    TEST_STATE.Tests_passed.name,
]

MERGE_INCORRECT_NAMES = [
    TEST_STATE.Tests_failed.name,
]

MERGE_UNHANDLED_NAMES = [
    MERGE_STATE.Merge_failed.name,
    MERGE_STATE.Merge_timedout.name,
]

UNDESIRABLE_STATES = [
    TEST_STATE.Git_checkout_failed.name,
    TEST_STATE.Not_tested.name,
    TEST_STATE.Tests_timedout.name,
    MERGE_STATE.Git_checkout_failed.name,
]


main_branch_names = ["main", "refs/heads/main", "master", "refs/heads/master"]


def build_table1(
    result_df: pd.DataFrame,
    merge_tools: List[str],
    correct: List[int],
    unhandled: List[int],
    incorrect: List[int],
) -> str:
    """Build a table with the results of the merge tools.
    Args:
        result_df: DataFrame containing the results of the merge tools
        merge_tools: list of merge tools
        correct: list of correct merges
        unhandled: list of unhandled merges
        incorrect: list of incorrect merges
    Returns:
        LaTeX table with the results of the merge tools
    """
    # Table overall results
    table = """% Do not edit.  This file is automatically generated.
\\begin{tabular}{l|c c|c c|c c|}
        Tool & \\multicolumn{6}{c|}{Merges} \\\\ \\cline{2-7}
        & \\multicolumn{2}{c|}{Correct} &
        \\multicolumn{2}{c|}{Unhandled} &
        \\multicolumn{2}{c|}{Incorrect} \\\\
        & \\# & \\% & \\# & \\% & \\# & \\% \\\\
        \\hline\n"""
    total = len(result_df)
    for merge_tool_idx, merge_tool in enumerate(merge_tools):
        correct_percentage = 100 * correct[merge_tool_idx] / total if total != 0 else 0
        unhandled_percentage = (
            100 * unhandled[merge_tool_idx] / total if total != 0 else 0
        )
        incorrect_percentage = (
            100 * incorrect[merge_tool_idx] / total if total != 0 else 0
        )
        table += f"{merge_tool_latex_name(merge_tool):32}"
        table += f" & {correct[merge_tool_idx]:5} & {round(correct_percentage):3}\\%"
        table += (
            f" & {unhandled[merge_tool_idx]:5} & {round(unhandled_percentage):3}\\%"
        )
        table += f" & {incorrect[merge_tool_idx]:5} & {round(incorrect_percentage):3}\\% \\\\\n"
    table += "\\end{tabular}\n"
    return table


def build_table2(main_df: pd.DataFrame, merge_tools: List[str], feature) -> str:
    """Build a table with the results of the merge tools.
    Args:
        main: DataFrame containing the results of the merge tools for the main branch
        merge_tools: list of merge tools
        feature: DataFrame containing the results of the merge tools for the other branches
    Returns:
        LaTeX table with the results of the merge tools
    """
    table2 = """% Do not edit.  This file is automatically generated.
\\setlength{\\tabcolsep}{.285\\tabcolsep}
\\begin{tabular}{c|cc|cc|cc}
            Tool &
            \\multicolumn{6}{c}{Merges} \\\\ \\cline{2-7}
            &
            \\multicolumn{2}{c|}{Correct} &
            \\multicolumn{2}{c|}{Unhandled} &
            \\multicolumn{2}{c}{Incorrect} \\\\
            &
            \\multicolumn{1}{c}{Main} &
            \\multicolumn{1}{c|}{Other} &
            \\multicolumn{1}{c}{Main} &
            \\multicolumn{1}{c|}{Other} &
            \\multicolumn{1}{c}{Main} &
            \\multicolumn{1}{c}{Other} \\\\
            \\hline\n"""

    for _, merge_tool in enumerate(merge_tools):
        merge_main = main_df[merge_tool]
        merge_feature = feature[merge_tool]

        correct_main = sum(val in MERGE_CORRECT_NAMES for val in merge_main)
        correct_main_percentage = (
            100 * correct_main / len(main_df) if len(main_df) != 0 else 0
        )
        correct_feature = sum(val in MERGE_CORRECT_NAMES for val in merge_feature)
        correct_feature_percentage = (
            100 * correct_feature / len(feature) if len(feature) > 0 else -1
        )

        incorrect_main = sum(val in MERGE_INCORRECT_NAMES for val in merge_main)
        incorrect_main_percentage = (
            100 * incorrect_main / len(main_df) if len(main_df) != 0 else 0
        )
        incorrect_feature = sum(val in MERGE_INCORRECT_NAMES for val in merge_feature)
        incorrect_feature_percentage = (
            100 * incorrect_feature / len(feature) if len(feature) > 0 else -1
        )

        unhandled_main = sum(val in MERGE_UNHANDLED_NAMES for val in merge_main)
        unhandled_main_percentage = (
            100 * unhandled_main / len(main_df) if len(main_df) != 0 else 0
        )
        unhandled_feature = sum(val in MERGE_UNHANDLED_NAMES for val in merge_feature)
        unhandled_feature_percentage = (
            100 * unhandled_feature / len(feature) if len(feature) > 0 else -1
        )

        table2 += f"            {merge_tool_latex_name(merge_tool):32}"
        table2 += f" & {round(correct_main_percentage):3}\\%"
        table2 += f" & {round(correct_feature_percentage):3}\\%"
        table2 += f" & {round(unhandled_main_percentage):3}\\%"
        table2 += f" & {round(unhandled_feature_percentage):3}\\%"
        table2 += f" & {round(incorrect_main_percentage):3}\\%"
        table2 += f" & {round(incorrect_feature_percentage):3}\\% \\\\\n"

    table2 += "\\end{tabular}\n"
    return table2


# Create a 2D comparison table
def create_comparison_table(df: pd.DataFrame, merge_tools: List[str]) -> pd.DataFrame:
    all_tools = [tool for tool in merge_tools]
    comparison_table = pd.DataFrame(index=all_tools, columns=all_tools)

    for tool1 in merge_tools:
        for tool2 in merge_tools:
            if tool1 != tool2:
                # Count where tool1 is incorrect and tool2 is unhandled
                count = (
                    (df[tool1].isin(MERGE_INCORRECT_NAMES))
                    & (df[tool2].isin(MERGE_UNHANDLED_NAMES))
                ).sum()
                comparison_table.loc[tool1, tool2] = count
            else:
                comparison_table.loc[tool1, tool2] = "-"

    return comparison_table


def main():
    """Main function"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_name", type=str, default="combined")
    parser.add_argument(
        "--full_repos_csv",
        type=Path,
        default=Path("input_data/repos_combined_with_hashes.csv"),
    )
    parser.add_argument(
        "--repos_head_passes_csv",
        type=Path,
        default=Path("results/combined/repos_head_passes.csv"),
    )
    parser.add_argument(
        "--tested_merges_path",
        type=Path,
        default=Path("results/combined/merges_tested"),
    )
    parser.add_argument(
        "--merges_path", type=Path, default=Path("results/combined/merges")
    )
    parser.add_argument(
        "--analyzed_merges_path",
        type=Path,
        default=Path("results/combined/merges_analyzed"),
    )
    parser.add_argument(
        "--manual_override_csv",
        type=Path,
        help="Path to the manual override CSV file",
        default=Path("results/manual_override.csv"),
    )
    parser.add_argument("--test_cache_dir", type=Path, default=Path("cache/test_cache"))
    parser.add_argument("--n_merges", type=int, default=100)
    parser.add_argument("--output_dir", type=Path, default=Path("results/combined"))
    parser.add_argument("--timed_merges_path", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output_dir

    # Combine results file
    result_df_list = []
    repos = pd.read_csv(args.repos_head_passes_csv, index_col="idx")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("Processing repos...", total=len(repos))
        for _, repository_data in repos.iterrows():
            progress.update(task, advance=1)
            repo_slug = repository_data["repository"]
            merge_list_file = args.tested_merges_path / (repo_slug + ".csv")
            if not merge_list_file.exists():
                raise ValueError(
                    "latex_ouput.py:",
                    repo_slug,
                    "does not have a list of merges. Missing file: ",
                    merge_list_file,
                )

            try:
                merges = pd.read_csv(merge_list_file, header=0, index_col="idx")
                if len(merges) == 0:
                    continue
            except pd.errors.EmptyDataError:
                continue
            merges = merges[merges["parents pass"]]
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
    result_df.index = (
        result_df["repo-idx"].astype(str) + "-" + result_df["merge-idx"].astype(str)  # type: ignore
    )

    # Remove undesired states
    for merge_tool in MERGE_TOOL:
        result_df = result_df[~result_df[merge_tool.name].isin(UNDESIRABLE_STATES)]

    # Apply manual overrides if the file exists
    if args.manual_override_csv and args.manual_override_csv.exists():
        manual_overrides = pd.read_csv(args.manual_override_csv)
        for _, override in manual_overrides.iterrows():
            repo_slug = override["repository"]
            left = override["left"]
            right = override["right"]
            merge = override["merge"]

            # Find the corresponding row in result_df
            mask = (
                (result_df["repository"] == repo_slug)
                & (result_df["left"] == left)
                & (result_df["right"] == right)
                & (result_df["merge"] == merge)
            )

            if mask.sum() == 1:
                # Apply the override for each column specified in the manual override CSV
                for col in override.index:
                    if col not in ["repository", "left", "right", "merge"]:
                        # Check if the value is not empty (not ,,)
                        if pd.notna(override[col]) and override[col] != "":
                            result_df.loc[mask, col] = override[col]
            elif mask.sum() > 1:
                raise ValueError(
                    f"Multiple matches found for {repo_slug}, {left}, {right}, {merge}. Skipping this override."
                )
            else:
                logger.info(
                    f"Warning: No match found for {repo_slug}, {left}, {right}, {merge}. Skipping this override."
                )

    # Create a csv for results with both unhandled and incorrect merges without intellimerge
    considered_merge_tools = [
        merge_tool.name
        for merge_tool in MERGE_TOOL
        if merge_tool != MERGE_TOOL.intellimerge
    ]
    unhandled_mask = (
        result_df[considered_merge_tools].isin(MERGE_UNHANDLED_NAMES).any(axis=1)
    )
    incorrect_mask = (
        result_df[considered_merge_tools].isin(MERGE_INCORRECT_NAMES).any(axis=1)
    )
    filtered_df = result_df[unhandled_mask & incorrect_mask]
    csv_filename = (
        args.output_dir / "unhandled_and_failed_merges_without_intellimerge.csv"
    )
    filtered_df.to_csv(csv_filename, index=False)

    # Create a csv for results with both unhandled and incorrect merges without intellimerge and spork
    considered_merge_tools = [
        merge_tool.name
        for merge_tool in MERGE_TOOL
        if merge_tool != MERGE_TOOL.intellimerge and merge_tool != MERGE_TOOL.spork
    ]
    unhandled_mask = (
        result_df[considered_merge_tools].isin(MERGE_UNHANDLED_NAMES).any(axis=1)
    )
    incorrect_mask = (
        result_df[considered_merge_tools].isin(MERGE_INCORRECT_NAMES).any(axis=1)
    )
    filtered_df = result_df[unhandled_mask & incorrect_mask]
    csv_filename = (
        args.output_dir
        / "unhandled_and_failed_merges_without_intellimerge_and_spork.csv"
    )
    filtered_df.to_csv(csv_filename, index=False)

    print(f"CSV saved to: {csv_filename}")
    print(f"Rows: {len(filtered_df)}")

    result_df.to_csv(args.output_dir / "result.csv", index_label="idx")

    main_df = result_df[result_df["branch_name"].isin(main_branch_names)]
    feature = result_df[~result_df["branch_name"].isin(main_branch_names)]

    for plot_category, merge_tools in PLOTS.items():
        plots_output_path = output_dir / "plots" / plot_category
        tables_output_path = output_dir / "tables" / plot_category
        Path(plots_output_path).mkdir(parents=True, exist_ok=True)
        Path(tables_output_path).mkdir(parents=True, exist_ok=True)

        check_fingerprint_consistency(result_df, merge_tools)

        # Generate the comparison table
        comparison_table = create_comparison_table(result_df, merge_tools)

        # Save the comparison table as a separate .tex file
        with open(
            tables_output_path / "tool_comparison_table.tex", "w", encoding="utf-8"
        ) as file:
            file.write("% Do not edit. This file is automatically generated.\n")
            file.write("\\begin{table}[h]\n")
            file.write("\\centering\n")
            file.write(
                "\\caption{Comparison of Merge Tool Results: Incorrect vs Unhandled}\n"
            )
            file.write("\\label{tab:tool-comparison}\n")
            file.write("\\small\n")
            file.write("\\begin{tabular}{l" + "r" * len(merge_tools) + "}\n")
            file.write("\\toprule\n")
            file.write(
                "& "
                + " & ".join([merge_tool_latex_name(tool) for tool in merge_tools])
                + " \\\\\n"
            )
            file.write("\\midrule\n")

            for i, row in enumerate(comparison_table.index):
                row_values = [
                    str(val) if val != "-" else "-" for val in comparison_table.loc[row]
                ]
                file.write(
                    f"{merge_tool_latex_name(row)} & "
                    + " & ".join(row_values)
                    + " \\\\\n"
                )

            file.write("\\bottomrule\n")
            file.write("\\end{tabular}\n")
            file.write("\\end{table}\n")

        comparison_table.to_csv(tables_output_path / "tool_comparison_table.csv")

        # Figure Heat map diffing
        result = pd.DataFrame(
            {
                merge_tool: {merge_tool: 0 for merge_tool in merge_tools}
                for merge_tool in merge_tools
            }
        )
        for merge_tool1 in merge_tools:
            for merge_tool2 in merge_tools:
                # Mask for different fingerprints
                mask_diff_fingerprint = (
                    result_df[merge_tool1 + "_merge_fingerprint"]
                    != result_df[merge_tool2 + "_merge_fingerprint"]
                )

                # Mask if one of the results is in correct or incorrect names
                merge_name_flags1 = result_df[merge_tool1].isin(
                    MERGE_CORRECT_NAMES + MERGE_INCORRECT_NAMES
                )
                merge_name_flags2 = result_df[merge_tool2].isin(
                    MERGE_CORRECT_NAMES + MERGE_INCORRECT_NAMES
                )
                mask_merge_name = merge_name_flags1 | merge_name_flags2

                # Calculate the result
                result.loc[merge_tool1, merge_tool2] = (
                    mask_diff_fingerprint & mask_merge_name
                ).sum()

        # Transform the result into a numpy array
        _, ax = plt.subplots(figsize=(8, 6))
        result_array = np.tril(result.to_numpy())
        latex_merge_tool = [
            "\\mbox{" + merge_tool_latex_name(i) + "}" for i in result.columns
        ]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            heatmap = sns.heatmap(
                result_array,
                annot=True,
                ax=ax,
                xticklabels=latex_merge_tool,  # type: ignore
                yticklabels=latex_merge_tool,  # type: ignore
                mask=np.triu(np.ones_like(result, dtype=bool), k=1),
                cmap="Blues",
                annot_kws={"size": 8},
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
            "heatmap-img0.png", f"{plots_output_path}/heatmap-img0.png"
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
        max_cost_intersection = 0
        for idx, merge_tool in enumerate(merge_tools):
            if incorrect[idx] == 0:
                continue
            max_cost_intersection = max(
                max_cost_intersection,
                ((unhandled[idx] + incorrect[idx] + correct[idx]) - unhandled[idx])
                * 1.0
                / incorrect[idx],
            )

        _, ax = plt.subplots()
        for idx, merge_tool in enumerate(merge_tools):
            results = []
            for cost_factor in np.linspace(1, max_cost_intersection, 1000):
                score = unhandled[idx] * 1 + incorrect[idx] * cost_factor
                score = score / (unhandled[idx] + incorrect[idx] + correct[idx])
                score = 1 - score
                results.append(score)
            line_styles = [
                "-",
                ":",
                "--",
                "-.",
                (0, (1, 1)),
                (0, (5, 10)),
                (0, (5, 5)),
                (0, (3, 5, 1, 5)),
            ]
            line_style = line_styles[idx % len(line_styles)]
            ax.plot(
                np.linspace(1, max_cost_intersection, 1000),
                results,
                label=merge_tool_latex_name(merge_tool),
                linestyle=line_style,
                linewidth=2,
                alpha=0.8,
            )
        plt.xlabel("Incorrect merges cost factor $k$")
        plt.ylabel("\\mbox{Effort Reduction}")
        plt.xlim(0, 12.5)
        plt.ylim(0.2, 0.5)
        plt.legend()
        plt.tight_layout()
        plt.savefig(plots_output_path / "cost_without_manual.pgf")
        plt.savefig(plots_output_path / "cost_without_manual.pdf")

        # Cost plot with manual merges
        ax.plot(
            np.linspace(1, max_cost_intersection, 1000),
            np.zeros(1000),
            label="Manual Merging",
            color="red",
        )
        plt.xlim(0, max_cost_intersection)
        plt.ylim(-0.02, 0.6)
        plt.legend()
        plt.tight_layout()
        plt.savefig(plots_output_path / "cost_with_manual.pgf")
        plt.savefig(plots_output_path / "cost_with_manual.pdf")

        # Table results
        with open(
            tables_output_path / "table_summary.tex", "w", encoding="utf-8"
        ) as file:
            file.write(
                build_table1(result_df, merge_tools, correct, unhandled, incorrect)
            )

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

        logger.success(my_table)

        # Table by merge source
        with open(
            tables_output_path / "table_feature_main_summary.tex",
            "w",
            encoding="utf-8",
        ) as file:
            file.write(build_table2(main_df, merge_tools, feature))

        # Table run time
        if args.timed_merges_path:
            table3 = """% Do not edit.  This file is automatically generated.
\\begin{tabular}{c|c|c|c}
    & \\multicolumn{3}{c}{Run time (seconds)} \\\\
    Tool & Mean & Median & Max \\\\
    \\hline\n"""
            timed_df = []
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task("Processing timed merges...", total=len(repos))
                for _, repository_data in repos.iterrows():
                    progress.update(task, advance=1)
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

    # Assuming args.merges_path and other variables are defined elsewhere in your code
    count_merges_initial = 0
    count_non_trivial_merges = 0
    count_non_trivial_repos = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(
            "Processing merges...", total=len(repos_head_passes_df)
        )
        for _, repository_data in repos_head_passes_df.iterrows():
            progress.update(task, advance=1)
            merge_list_file = args.merges_path / (
                repository_data["repository"] + ".csv"
            )
            if not os.path.isfile(merge_list_file):
                continue
            try:
                df = pd.read_csv(merge_list_file, index_col=0)
            except pd.errors.EmptyDataError:
                continue
            # Ensure notes column is treated as string
            df["notes"] = df["notes"].astype(str)
            count_merges_initial += len(df)
            # Use na=False to handle NaN values properly
            non_trivial_mask = df["notes"].str.contains(
                "a parent is the base", na=False
            )
            count_non_trivial_merges += non_trivial_mask.sum()
            count_non_trivial_repos += non_trivial_mask.any()

    # Assuming output and latex_def functions are defined elsewhere in your code
    output += latex_def(run_name_camel_case + "MergesInitial", count_merges_initial)
    output += latex_def(run_name_camel_case + "MergesPer", args.n_merges)
    output += latex_def(
        run_name_camel_case + "MergesNonTrivial", count_non_trivial_merges
    )
    output += latex_def(
        run_name_camel_case + "ReposNonTrivial", count_non_trivial_repos
    )

    count_merges_java_diff = 0
    count_repos_merges_java_diff = 0
    count_merges_diff_and_parents_pass = 0
    count_repos_merges_diff_and_parents_pass = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(
            "Processing merges...", total=len(repos_head_passes_df)
        )
        for _, repository_data in repos_head_passes_df.iterrows():
            progress.update(task, advance=1)
            merge_list_file = args.analyzed_merges_path / (
                repository_data["repository"] + ".csv"
            )
            if not os.path.isfile(merge_list_file):
                continue
            try:
                df = pd.read_csv(merge_list_file, index_col=0)
            except pd.errors.EmptyDataError:
                continue
            if len(df) == 0:
                continue
            count_merges_java_diff += df["diff contains java file"].dropna().sum()
            count_merges_diff_and_parents_pass += df["test merge"].dropna().sum()
            if df["diff contains java file"].dropna().sum() > 0:
                count_repos_merges_java_diff += 1
            if df["test merge"].dropna().sum() > 0:
                count_repos_merges_diff_and_parents_pass += 1

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
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(
            "Processing merges...", total=len(repos_head_passes_df)
        )
        for _, repository_data in repos_head_passes_df.iterrows():
            progress.update(task, advance=1)
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
            # Makre sure each element has "parents pass" set to True
            for _, merge in merges.iterrows():
                assert merge["parents pass"]
                assert merge["test merge"]
                assert merge["diff contains java file"]
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

    manual_override_set = set()
    if args.manual_override_csv and args.manual_override_csv.exists():
        manual_overrides = pd.read_csv(args.manual_override_csv)
        manual_override_set = set(
            (row["repository"], row["left"], row["right"], row["merge"])
            for _, row in manual_overrides.iterrows()
        )

    tries = []
    for idx, merge in result_df.iterrows():
        for merge_tool in MERGE_TOOL:
            if merge[merge_tool.name] != TEST_STATE.Tests_passed.name:
                continue

            # Ignore entry if it is contained in the manual override CSV
            if (
                merge["repository"],
                merge["left"],
                merge["right"],
                merge["merge"],
            ) in manual_override_set:
                continue

            # Load cached test results
            cache_entry = lookup_in_cache(
                cache_key=merge[merge_tool.name + "_merge_fingerprint"],
                repo_slug=merge["repository"],
                cache_directory=args.test_cache_dir,
                set_run=False,
            )
            tries.append(len(cache_entry["test_results"]))  # type: ignore
    average_tries = sum(tries) / len(tries) if len(tries) > 0 else 0
    output += latex_def(run_name_camel_case + "AverageTriesUntilPass", average_tries)
    # Output the number of merges for each amount of tries before pass
    tries_count = {}
    for t in tries:
        if t not in tries_count:
            tries_count[t] = 0
        tries_count[t] += 1
    for t in tries_count:
        output += latex_def(
            run_name_camel_case + f"NumberofMergesWith{t}TriesUntilPass",
            tries_count.get(t, 0),
        )

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

    output += latex_def(run_name_camel_case + "MainBranchMerges", len(main_df))
    output += latex_def(
        run_name_camel_case + "MainBranchMergesPercent",
        round(len(main_df) * 100 / len(result_df)),
    )
    output += latex_def(run_name_camel_case + "OtherBranchMerges", len(feature))
    output += latex_def(
        run_name_camel_case + "OtherBranchMergesPercent",
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
