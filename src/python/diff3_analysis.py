"""Runs a merge and uses diff3 to compare it to the base and final branch of a given repo.
See readme for details on shell scripts to run these methods.
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


def diff3_analysis(merge_tool: str, results_index: int, repo_output_dir):
    """
    Analyzes merge conflicts using the diff3 tool and opens the results in the default text viewer.

    Args:
        merge_tool (str): The merge tool to be used.
        results_index (int): The index of the repository in the results DataFrame.
        repo_output_dir (path): The path of where we want to store the results from the analysis

    Returns:
        None
    """

    # Deletes base, programmer_merge, and merge_attempt folders in repos dir
    # We do this to prevent errors if cloning the same repo into the folder twice
    shutil.rmtree("./repos", ignore_errors=True)

    # Retrieve left and right branch from hash in repo
    df = pd.read_csv("../../results/combined/result.csv")
    repo_name = df.iloc[results_index]["repository"]

    script = "../scripts/merge_tools/" + merge_tool + ".sh"
    repo = clone_repo_to_path(
        repo_name, "./repos/merge_attempt"
    )  # Return a Git-Python repo object
    repo.remote().fetch()
    left_sha = df.iloc[results_index]["left"]
    repo.git.checkout(left_sha, force=True)
    print("Checking out left" + left_sha)
    repo.submodule_update()
    repo.git.checkout("-b", "TEMP_LEFT_BRANCH", force=True)
    repo.git.checkout(df.iloc[results_index]["right"], force=True)
    print("Checking out right" + df.iloc[results_index]["right"])
    repo.submodule_update()
    repo.git.checkout("-b", "TEMP_RIGHT_BRANCH", force=True)

    base_sha = subprocess.run(
        [
            "git",
            "merge-base",
            "TEMP_LEFT_BRANCH",
            "TEMP_RIGHT_BRANCH",
        ],
        cwd="./repos/merge_attempt/" + repo_name,
        stdout=subprocess.PIPE,
        text=True,
    )
    print("Found base sha" + base_sha.stdout)

    repo2 = clone_repo_to_path(
        repo_name, "./repos/base"
    )  # Return a Git-Python repo object
    repo2.remote().fetch()
    base_sha = base_sha.stdout.strip()
    repo2.git.checkout(base_sha, force=True)
    repo2.submodule_update()

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

    repo3 = clone_repo_to_path(
        repo_name, "./repos/programmer_merge"
    )  # Return a Git-Python repo object
    repo3.git.checkout(df.iloc[results_index]["merge"], force=True)
    repo3.submodule_update()

    print(conflict_file_matches)

    for conflict_file_match in conflict_file_matches:
        print("HELLO!!!")
        conflicting_file = str(conflict_file_match)
        conflict_path = os.path.join(repo_name, conflicting_file)
        conflict_path_merge_attempt = os.path.join(
            "./repos/merge_attempt", conflict_path
        )

        conflict_path_base = os.path.join("./repos/base", conflict_path)
        conflict_path_programmer_merge = os.path.join(
            "./repos/programmer_merge", conflict_path
        )

        diff_results = subprocess.run(
            [
                "diff3",
                conflict_path_base,
                conflict_path_merge_attempt,
                conflict_path_programmer_merge,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Check that diff3 didn't run into missing files in the base
        error_message = "No such file or directory"
        if error_message in diff_results.stderr:
            print("WHERE WE NEED TO BE")
            # Since the conflict file was added in both parents we can't diff the base.
            diff_results = subprocess.run(
                [
                    "diff",
                    conflict_path_merge_attempt,
                    conflict_path_programmer_merge,
                ],
                stdout=subprocess.PIPE,
                text=True,
            )

        # Generate a filename for the diff result, including the new subdirectory
        diff_filename = os.path.join(
            repo_output_dir, f"diff_{os.path.basename(conflicting_file)}.txt"
        )

        # Ensure the output directory exists
        os.makedirs(diff_filename, exist_ok=True)

        # Write the diff results to the file
        with open(diff_filename, "w") as diff_file:
            diff_file.write(diff_results.stdout)

        # Optionally, print or log the path of the diff file
        print(f"Diff results saved to {diff_filename}")


def main(merge_tool: str, results_index: int, repo_output_dir: str):
    """
    Entry point for the script when run from the command line.
    """
    # Convert results_index to int here if using argparse
    diff3_analysis(merge_tool, results_index, repo_output_dir)


if __name__ == "__main__":
    # Use argparse to parse command line arguments
    parser = argparse.ArgumentParser(
        description="Analyze merge conflicts using the diff3 tool."
    )
    parser.add_argument("merge_tool", type=str, help="The merge tool to be used.")
    parser.add_argument(
        "results_index",
        type=int,
        help="The index of the repository in the results DataFrame.",
    )
    parser.add_argument(
        "repo_output_dir",
        type=str,
        help="The path of where we want to store the results from the analysis.",
    )

    args = parser.parse_args()

    # Ensure the output directory exists
    os.makedirs(args.repo_output_dir, exist_ok=True)

    # Call main function with parsed arguments
    main(args.merge_tool, args.results_index, args.repo_output_dir)
