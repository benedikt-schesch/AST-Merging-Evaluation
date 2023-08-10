"""
This script contains the Repository class that represents a repository.
It also contains the functions that are used to test the repository.
"""

from pathlib import Path
from typing import Union, Tuple
from enum import Enum
import uuid
import subprocess
import shutil
import time
from git.repo import Repo
from cache_utils import (
    get_cache_path,
    check_cache,
    get_cache,
    write_cache,
    get_cache_lock,
)

DELETE_WORKDIRS = True
REPOS_PATH = Path("repos")
WORKDIR_PREFIX = Path(".workdir")
TEST_STATE = Enum(
    "TEST_STATE",
    [
        "Tests_passed",
        "Tests_failed",
        "Tests_running",
        "Tests_timedout",
        "Git_checkout_failed",
    ],
)
BRANCH_BASE_NAME = "___MERGE_TESTER"
LEFT_BRANCH_NAME = BRANCH_BASE_NAME + "_LEFT"
RIGHT_BRANCH_NAME = BRANCH_BASE_NAME + "_RIGHT"
MERGE_TOOL = Enum(
    "MERGE_TOOL",
    [
        "gitmerge_ort",
        "gitmerge_ort_ignorespace",
        "gitmerge_recursive_patience",
        "gitmerge_recursive_minimal",
        "gitmerge_recursive_histogram",
        "gitmerge_recursive_myers",
        # "gitmerge_resolve",
        "git_hires_merge",
        "spork",
        "intellimerge",
    ],
)
MERGE_STATE = Enum(
    "MERGE_STATE",
    [
        "Merge_failed",
        "Merge_timedout",
        "Merge_success",
        "git_checkout_failed",
    ],
)


def repo_test(repo_dir_copy: Path, timeout: int) -> Tuple[TEST_STATE, str]:
    """Returns the result of run_repo_tests.sh on the given working copy.
    If one test passes then the entire test is marked as passed.
    If one test timeouts then the entire test is marked as timeout.
    Args:
        repo_dir_copy (Path): The path of the working copy (the clone).
        timeout (int): Test Timeout limit.
    Returns:
        TEST_STATE: The result of the test.
        str: explanation. The explanation of the result.
    """
    explanation = ""
    command = [
        "src/scripts/run_repo_tests.sh",
        str(repo_dir_copy),
    ]
    try:
        p = subprocess.run(  # pylint: disable=consider-using-with
            command,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        explanation = "Run Command: " + " ".join(command) + "\nTimed out"
        explanation += "\nstdout:\n" + e.stdout.decode("utf-8") if e.stdout else ""
        explanation += "\nstderr:\n" + e.stderr.decode("utf-8") if e.stderr else ""
        return TEST_STATE.Tests_timedout, explanation
    rc = p.returncode
    stdout = p.stdout.decode("utf-8")
    stderr = p.stderr.decode("utf-8")
    explanation = (
        "Run Command: "
        + " ".join(command)
        + "\nstdout:\n"
        + stdout
        + "\nstderr:\n"
        + stderr
    )
    if rc == 0:  # Success
        return TEST_STATE.Tests_passed, explanation
    return TEST_STATE.Tests_failed, explanation


class Repository:
    """A class that represents a repository."""

    def __init__(
        self, repo_name: str, cache_prefix: Path, workdir: Union[Path, None] = None
    ) -> None:
        """Initializes the repository.
        Args:
            repo_name (str): The name of the repository.
            cache_prefix (Path): The prefix of the cache.
            workdir (Union[Path,None], optional) = None: Folder to use in the WORKDIR_PREFIX.
        """
        self.repo_name = repo_name
        self.path = REPOS_PATH / repo_name
        if workdir is None:
            self.workdir = WORKDIR_PREFIX / uuid.uuid4().hex
        else:
            self.workdir = WORKDIR_PREFIX / workdir
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.repo_path = self.workdir / self.path.name
        shutil.copytree(self.path, self.repo_path)
        self.repo = Repo(self.repo_path)
        self.cache_prefix = cache_prefix

    def checkout(self, commit: str) -> Tuple[bool, str]:
        """Checks out the given commit.
        Args:
            commit (str): The commit to checkout.
        Returns:
            bool: True if the checkout succeeded, False otherwise.
        """
        try:
            self.repo.git.checkout(commit, force=True)
            self.repo.submodule_update()
        except Exception as e:
            explanation = (
                "Failed to checkout "
                + commit
                + " for "
                + self.repo_name
                + " : \n"
                + str(e)
            )
            return False, explanation
        return True, ""

    def merge(
        self,
        tool: MERGE_TOOL,
        left_commit: str,
        right_commit: str,
        timeout: int,
    ) -> Tuple[
        MERGE_STATE, Union[str, None], Union[str, None], Union[str, None], str, float
    ]:
        """Merges the given commits using the given tool.
        Args:
            tool (MERGE_TOOL): The tool to use.
            left_commit (str): The left commit to merge.
            right_commit (str): The right commit to merge.
            timeout (int): The timeout limit.
        Returns:
            MERGE_STATE: The result of the merge.
            str: The tree fingerprint of result.
            str: The left fingerprint.
            str: The right fingerprint.
            str: explanation. The explanation of the result.
            float: The time it took to run the merge.
        """
        success, explanation = self.checkout(left_commit)
        left_fingreprint = self.compute_tree_fingerprint()
        if not success:
            return MERGE_STATE.git_checkout_failed, None, None, None, explanation, -1
        self.repo.git.checkout("-b", LEFT_BRANCH_NAME, force=True)
        success, explanation = self.checkout(right_commit)
        right_fingerprint = self.compute_tree_fingerprint()
        if not success:
            return (
                MERGE_STATE.git_checkout_failed,
                None,
                left_fingreprint,
                None,
                explanation,
                -1,
            )
        self.repo.git.checkout("-b", RIGHT_BRANCH_NAME, force=True)
        start = time.time()
        try:
            command = [
                "src/scripts/merge_tools/" + tool.name.replace("_", "-") + ".sh",
                self.repo_path,
                LEFT_BRANCH_NAME,
                RIGHT_BRANCH_NAME,
            ]
            p = subprocess.run(  # pylint: disable=consider-using-with
                command,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            explanation = "Run Command: " + " ".join(command) + "\nTimed out"
            explanation += "\nstdout:\n" + e.stdout.decode("utf-8") if e.stdout else ""
            explanation += "\nstderr:\n" + e.stderr.decode("utf-8") if e.stderr else ""
            sha = self.compute_tree_fingerprint()
            return (
                MERGE_STATE.Merge_timedout,
                sha,
                left_fingreprint,
                right_fingerprint,
                explanation,
                -1,
            )
        run_time = time.time() - start
        explanation = "STDOUT:\n" + p.stdout.decode("utf-8")
        explanation += "\nSTDERR:\n" + p.stderr.decode("utf-8")
        merge_status = (
            MERGE_STATE.Merge_success if p.returncode == 0 else MERGE_STATE.Merge_failed
        )
        sha = self.compute_tree_fingerprint()
        return (
            merge_status,
            sha,
            left_fingreprint,
            right_fingerprint,
            explanation,
            run_time,
        )

    def compute_tree_fingerprint(self) -> str:
        """Computes the tree fingerprint of the repository.
        Args:
            store_cache (bool, optional) = False: Whether to store the fingerprint in the cache.
        Returns:
            str: The tree fingerprint.
        """
        assert self.repo_path.exists()
        command = (
            "sha256sum <(cd "
            + str(self.repo_path)
            + " ;find . -type f -not -path '*/\\.git*' -exec sha256sum {} \\; | sort)"
        )
        result = (
            subprocess.check_output(command, shell=True, executable="/bin/bash")
            .decode("utf-8")
            .split()[0]
        )
        return result

    def test(self, timeout: int, n_restarts: int) -> TEST_STATE:
        """Tests the repository.
        Args:
            timeout (int): The timeout limit.
            n_restarts (int): The number of times to restart the test.
        Returns:
            TEST_STATE: The result of the test.
        """
        sha = self.compute_tree_fingerprint()
        cache_entry = get_cache_path(self.repo_name, self.cache_prefix)
        cache_entry.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {}

        lock = get_cache_lock(self.repo_name, self.cache_prefix)
        with lock:
            if check_cache(sha, self.repo_name, self.cache_prefix):
                cache_data = get_cache(sha, self.repo_name, self.cache_prefix)
                return TEST_STATE[cache_data["test_result"]]
            cache_data["test_result"] = TEST_STATE.Tests_running.name
            write_cache(sha, cache_data, self.repo_name, self.cache_prefix)

        cache_data["test_results"] = []
        cache_data["test_log_file"] = []
        for i in range(n_restarts):
            test, explanation = repo_test(self.repo_path, timeout)
            test_log_file = Path(
                str(cache_entry).replace(".json", "_" + str(i) + ".log")
            )
            test_log_file.parent.mkdir(parents=True, exist_ok=True)
            if test_log_file.exists():
                test_log_file.unlink()
            with open(test_log_file, "w") as f:
                f.write(explanation)
            cache_data["test_results"].append(test.name)
            cache_data["test_log_file"].append(str(test_log_file))
            cache_data["test_result"] = test.name
            if test in (TEST_STATE.Tests_passed, TEST_STATE.Tests_timedout):
                break

        with lock:
            write_cache(
                sha, cache_data, self.repo_name, self.cache_prefix, overwrite=True
            )
        return TEST_STATE[cache_data["test_result"]]

    def __del__(self) -> None:
        """Deletes the repository."""
        if DELETE_WORKDIRS:
            shutil.rmtree(self.workdir)
