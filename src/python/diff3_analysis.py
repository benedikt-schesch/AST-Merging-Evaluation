"""Runs a merge and uses diff to compare it to the base and final branch of a given repo.
"""
import subprocess
import re
import os
import tempfile
import pandas as pd
from validate_repos import clone_repo_to_path
from merge_tester import MERGE_STATE


# pylint: disable=too-many-locals
def diff3_analysis(merge_tool: str, repo_num: int):
    """
    Analyzes merge conflicts using the diff3 tool and opens the results in the default text viewer.

    Args:
        merge_tool (str): The merge tool to be used.
        repo_num (int): The index of the repository in the results DataFrame.

    Returns:
        None
    """
    df = pd.read_csv("../../results/result.csv")
    repo_name = df.iloc[repo_num]["repo_name"]

    script = "../scripts/merge_tools/" + merge_tool + ".sh"
    repo = clone_repo_to_path(
        repo_name, "./repos/merge_attempt"
    )  # Return a Git-Python repo object
    repo.remote().fetch()
    left_sha = df.iloc[repo_num]["left"]
    repo.git.checkout(left_sha, force=True)
    repo.submodule_update()
    repo.git.checkout("-b", "TEMP_LEFT_BRANCH", force=True)
    repo.git.checkout(df.iloc[repo_num]["right"], force=True)
    repo.submodule_update()
    repo.git.checkout("-b", "TEMP_RIGHT_BRANCH", force=True)

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
    conflict_file_match = re.search(
        r"CONFLICT \(.+\): Merge conflict in (.+)", result.stdout
    )

    if conflict_file_match:
        conflicting_file = conflict_file_match.group(1)
        conflict_path = os.path.join(repo_name, conflicting_file)
        conflict_path_merge_attempt = os.path.join(
            "./repos/merge_attempt", conflict_path
        )

        repo = clone_repo_to_path(
            repo_name, "./repos/base"
        )  # Return a Git-Python repo object
        repo.remote().fetch()
        repo.git.checkout(df.iloc[repo_num]["base"], force=True)
        repo.submodule_update()
        conflict_path_base = os.path.join("./repos/base", conflict_path)

        repo = clone_repo_to_path(
            repo_name, "./repos/merge"
        )  # Return a Git-Python repo object
        repo.remote().fetch()
        repo.git.checkout(df.iloc[repo_num]["merge"], force=True)
        repo.submodule_update()
        conflict_path_merge = os.path.join("./repos/merge", conflict_path)

        diff_results = subprocess.run(
            [
                "diff3",
                conflict_path_base,
                conflict_path_merge_attempt,
                conflict_path_merge,
            ],
            stdout=subprocess.PIPE,
            text=True,
        )

        # Use a temporary file to store the diff results
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
            temp_file.write(diff_results.stdout)

        # Open the saved text file with the default application
        subprocess.run(["xdg-open", temp_file.name], check=True)

        # Delete the temporary file
        os.remove(temp_file.name)

    else:
        print("No conflicting file found in the output.")
