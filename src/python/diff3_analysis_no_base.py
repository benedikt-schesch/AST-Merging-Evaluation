"""Runs a merge and uses diff3 to compare it to the base and final branch of a given repo.
"""
import subprocess
import re
import os
import shutil
import tempfile
import pandas as pd
from repo import clone_repo_to_path
from merge_tester import MERGE_STATE

# pylint: disable-msg=too-many-locals


def diff3_analysis_no_base(merge_tool: str, repo_num: int):
    """
    Analyzes merge conflicts using the diff3 tool and opens the results in the default text viewer.

    Args:
        merge_tool (str): The merge tool to be used.
        repo_num (int): The index of the repository in the results DataFrame.

    Returns:
        None
    """
    shutil.rmtree("./repos", ignore_errors=True)

    df = pd.read_csv("../../results_greatest_hits/result.csv")
    repo_name = df.iloc[repo_num]["repository"]

    script = "../scripts/merge_tools/" + merge_tool + ".sh"
    repo = clone_repo_to_path(
        repo_name, "./repos/merge_attempt"
    )  # Return a Git-Python repo object
    repo.remote().fetch()
    left_sha = df.iloc[repo_num]["left"]
    repo.git.checkout(left_sha, force=True)
    print("Checking out left" + left_sha)
    repo.submodule_update()
    repo.git.checkout("-b", "TEMP_LEFT_BRANCH", force=True)
    repo.git.checkout(df.iloc[repo_num]["right"], force=True)
    print("Checking out right" + df.iloc[repo_num]["right"])
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

    conflict_file_matches = re.findall(
        r"CONFLICT \(.+\): Merge conflict in (.+)", result.stdout
    )

    print(result.stdout)

    repo = clone_repo_to_path(
        repo_name, "./repos/programmer_merge"
    )  # Return a Git-Python repo object
    repo.git.checkout(df.iloc[repo_num]["merge"], force=True)
    repo.submodule_update()


    for conflict_file_match in conflict_file_matches:
        conflicting_file = str(conflict_file_match)
        conflict_path = os.path.join(repo_name, conflicting_file)
        conflict_path_merge_attempt = os.path.join(
            "./repos/merge_attempt", conflict_path
        )

        conflict_path_programmer_merge = os.path.join(
            "./repos/programmer_merge", conflict_path
        )

        diff_results = subprocess.run(
            [
                "diff",
                conflict_path_merge_attempt,
                conflict_path_programmer_merge,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Use a temporary file to store the diff results
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
            temp_file.write(diff_results.stdout)

        # Open the saved text file with the default application
        subprocess.run(["xdg-open", temp_file.name], check=True)

        # Delete the temporary file
        os.remove(temp_file.name)

    # Deletes base, programmer_merge, and merge_attempt folders in repos dir
    # We do this to prevent errors if cloning the same repo into the folder twice
    '''
    subprocess.run(
        ["rm", "-rf", "./repos/base"],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    subprocess.run(
        ["rm", "-rf", "./repos/merge_attempt"],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    subprocess.run(
        ["rm", "-rf", "./repos/programmer_merge"],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    '''
