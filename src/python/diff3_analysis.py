"""
Recreates a merge and outputs the diff files for two algorithms for comparison on a given conflict.
Displays base, conflicting branches, and programmer merge.
See src/python/README.md for details on usage.
"""

import sys
import argparse
import subprocess
import re
import os
import shutil
import tempfile
import pandas as pd
from repo import clone_repo_to_path
from merge_tester import MERGE_STATE


# pylint: disable-msg=too-many-locals
# pylint: disable-msg=too-many-arguments


def setup_environment():
    """Remove repository directories to clean up the environment."""
    shutil.rmtree("./repos", ignore_errors=True)


def clone_and_checkout(repo_name, branch_sha, clone_dir):
    """
    Clone a repository to a specified path and checkout a given SHA.


    Args:
        repo_name (str): The repository to clone.
        branch_sha (str): The SHA commit or branch to checkout.
        clone_dir (str): Directory path to clone the repository.


    Returns:
        repo (GitPython.repo): The cloned repository object.
    """
    repo = clone_repo_to_path(repo_name, clone_dir)
    repo.remote().fetch()
    repo.git.checkout(branch_sha, force=True)
    repo.submodule_update()
    return repo


def process_diff(
    tool_name, base_path, attempt_path, merge_path, output_dir, index, filename
):
    """
    Process the diff between files and save the output to a designated file.

    Args:
        tool_name (str): Identifier for the merge tool.
        base_path (str): Path to the base file.
        attempt_path (str): Path to the merge attempt file.
        merge_path (str): Path to the manually merged file.
        output_dir (str): Directory where results will be saved.
        index (int): Index of the repository in the results list.
        filename (str): Base name for the output file.
    """
    # Run diff3 or fall back to diff if files are missing
    diff_results = subprocess.run(
        ["diff3", base_path, attempt_path, merge_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if "No such file or directory" in diff_results.stderr:
        diff_results = subprocess.run(
            ["diff", attempt_path, merge_path], stdout=subprocess.PIPE, text=True
        )

    # Prepare the output filename
    diff_filename = os.path.join(
        output_dir, str(index), tool_name, f"diff_{filename}.txt"
    )
    os.makedirs(
        os.path.dirname(diff_filename), exist_ok=True
    )  # Ensure the directory exists

    # Write the diff results to the file
    with open(diff_filename, "w") as diff_file:
        diff_file.write(diff_results.stdout)
    print(f"Diff results saved to {diff_filename}")


def diff3_analysis(
    merge_tool1: str, merge_tool2: str, results_index: int, repo_output_dir
):
    """
    Analyzes merge conflicts using the diff3 tool and opens the results in the default text viewer.
    Args:
        merge_tool1 (str): The merge tool that Merge_failed (tool name as written in spreadsheet)
        merge_tool2 (str): The merge tool that Failed_tests or Passed_tests
        results_index (int): The index of the repository in the results spreadsheet.
        repo_output_dir (path): The path of where we want to store the results from the analysis


    Returns:
        None
    """

    # Deletes base, programmer_merge, and merge_attempt folders in repos dir
    # We do this to prevent errors if cloning the same repo into the folder twice
    setup_environment()

    # Retrieve left and right branch from hash in repo
    df = pd.read_csv("../../results/combined/result.csv")
    repo_name = df.iloc[results_index]["repository"]

    script = "../scripts/merge_tools/" + merge_tool1 + ".sh"
    repo = clone_repo_to_path(
        repo_name, "./repos/merge_attempt1"
    )  # Return a Git-Python repo object
    repo.remote().fetch()
    left_sha = df.iloc[results_index]["left"]
    repo.git.checkout(left_sha, force=True)
    repo.submodule_update()
    repo.git.checkout("-b", "TEMP_LEFT_BRANCH", force=True)
    repo.git.checkout(df.iloc[results_index]["right"], force=True)
    repo.submodule_update()
    repo.git.checkout("-b", "TEMP_RIGHT_BRANCH", force=True)
    print("Checked out left and right")

    # Clone the base
    base_sha = subprocess.run(
        [
            "git",
            "merge-base",
            "TEMP_LEFT_BRANCH",
            "TEMP_RIGHT_BRANCH",
        ],
        cwd="./repos/merge_attempt1/" + repo_name,
        stdout=subprocess.PIPE,
        text=True,
    )
    print("Found base sha" + base_sha.stdout)
    base_sha = base_sha.stdout.strip()
    repo2 = clone_and_checkout(repo_name, base_sha, "./repos/base")

    # Recreate the merge
    result = subprocess.run(
        [
            script,
            repo.git.rev_parse("--show-toplevel"),
            "TEMP_LEFT_BRANCH",
            "TEMP_RIGHT_BRANCH",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )

    conflict_file_matches = re.findall(
        r"CONFLICT \(.+\): Merge conflict in (.+)", result.stdout
    )
    print(result.stdout)

    if conflict_file_matches == []:
        print("No conflict files to search")
        return

    repo3 = clone_and_checkout(
        repo_name, df.iloc[results_index]["merge"], "./repos/programmer_merge"
    )
    print(conflict_file_matches)

    script = "../scripts/merge_tools/" + merge_tool2 + ".sh"
    repo4 = clone_repo_to_path(
        repo_name, "./repos/merge_attempt2"
    )  # Return a Git-Python repo object
    repo4.remote().fetch()
    left_sha = df.iloc[results_index]["left"]
    repo4.git.checkout(left_sha, force=True)
    print("Checking out left" + left_sha)
    repo4.submodule_update()
    repo4.git.checkout("-b", "TEMP_LEFT_BRANCH", force=True)
    repo4.git.checkout(df.iloc[results_index]["right"], force=True)
    print("Checking out right" + df.iloc[results_index]["right"])
    repo4.submodule_update()
    repo4.git.checkout("-b", "TEMP_RIGHT_BRANCH", force=True)

    for conflict_file_match in conflict_file_matches:
        conflicting_file = str(conflict_file_match)
        conflict_path = os.path.join(repo_name, conflicting_file)
        conflict_file_base, _ = os.path.splitext(os.path.basename(conflicting_file))

        # Paths for the first merge attempt
        conflict_path_merge_attempt1 = os.path.join(
            "./repos/merge_attempt1", conflict_path
        )
        conflict_path_base = os.path.join("./repos/base", conflict_path)
        conflict_path_programmer_merge = os.path.join(
            "./repos/programmer_merge", conflict_path
        )

        # Process the first merge attempt
        process_diff(
            merge_tool1,
            conflict_path_base,
            conflict_path_merge_attempt1,
            conflict_path_programmer_merge,
            repo_output_dir,
            results_index,
            conflict_file_base,
        )

        """
       BREAK
       """

        # Paths for the second merge attempt
        conflict_path_merge_attempt2 = os.path.join(
            "./repos/merge_attempt2", conflict_path
        )

        # Process the second merge attempt
        process_diff(
            merge_tool2,
            conflict_path_base,
            conflict_path_merge_attempt2,
            conflict_path_programmer_merge,
            repo_output_dir,
            results_index,
            conflict_file_base,
        )


def main():
    """
    Parses arguments and calls diff3_analysis from the CLI
    """
    parser = argparse.ArgumentParser(
        description="Process and compare merge conflicts using two tools."
    )
    parser.add_argument("merge_tool1", type=str, help="The first merge tool to use")
    parser.add_argument("merge_tool2", type=str, help="The second merge tool to use")
    parser.add_argument(
        "results_index",
        type=int,
        help="The index of the repository in the results spreadsheet",
    )
    parser.add_argument(
        "repo_output_dir", type=str, help="The directory to store the results"
    )

    args = parser.parse_args()

    diff3_analysis(
        merge_tool1=args.merge_tool1,
        merge_tool2=args.merge_tool2,
        results_index=args.results_index,
        repo_output_dir=args.repo_output_dir,
    )


if __name__ == "__main__":
    main()
