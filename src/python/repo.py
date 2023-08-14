#!/usr/bin/env python3
"""
This script contains the Repository class that represents a repository.
It also contains the functions that are used to test the repository.
"""

from pathlib import Path
from typing import Union, Tuple
from enum import Enum
import uuid
import subprocess
import os
import shutil
import time
from git.repo import Repo
from cache_utils import (
    set_in_cache,
    check_and_load_cache,
)

CACHE_BACKOFF_TIME = 2 * 60  # 2 minutes
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
        "Not_tested",
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
        "gitmerge_ort_imports",
        "gitmerge_ort_imports_ignorespace",
        "gitmerge_recursive_patience",
        "gitmerge_recursive_minimal",
        "gitmerge_recursive_histogram",
        "gitmerge_recursive_myers",
        "gitmerge_resolve",
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
        "Git_checkout_failed",
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
        self,
        repo_name: str,
        cache_prefix: Path = Path(""),
        workdir: Union[Path, None] = None,
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
        self.test_cache_prefix = cache_prefix / "test_cache"
        self.sha_cache_prefix = cache_prefix / "sha_cache"

    def checkout(self, commit: str) -> Tuple[bool, str]:
        """Checks out the given commit.
        Args:
            commit (str): The commit to checkout.
        Returns:
            bool: True if the checkout succeeded, False otherwise.
            str: explanation. The explanation of the result.
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
            cache_entry = {"sha": None, "explanation": explanation}
            set_in_cache(commit, cache_entry, self.repo_name, self.sha_cache_prefix)
            return False, explanation
        cache_entry = {"sha": self.compute_tree_fingerprint(), "explanation": ""}
        set_in_cache(commit, cache_entry, self.repo_name, self.sha_cache_prefix)
        return True, ""

    def merge_and_test(  # pylint: disable=too-many-arguments
        self,
        tool: MERGE_TOOL,
        left_commit: str,
        right_commit: str,
        timeout: int,
        n_restarts: int,
    ) -> Tuple[
        Union[TEST_STATE, MERGE_STATE],
        Union[str, None],
        Union[str, None],
        Union[str, None],
        float,
    ]:
        """Merges the given commits using the given tool and tests the result.
        Args:
            tool (MERGE_TOOL): The tool to use.
            left_commit (str): The left commit to merge.
            right_commit (str): The right commit to merge.
            timeout (int): The timeout limit.
            n_restarts (int): The number of times to restart the test.
        Returns:
            TEST_STATE: The result of the test.
            str: The tree fingerprint of result.
            str: The left fingerprint.
            str: The right fingerprint.
            float: The time it took to run the merge.
        """
        (
            merge_status,
            merge_fingerprint,
            left_fingreprint,
            right_fingerprint,
            _,
            run_time,
        ) = self.merge(tool, left_commit, right_commit, -1)
        if merge_status != MERGE_STATE.Merge_success:
            return merge_status, None, None, None, -1
        test_result = self.test(timeout, n_restarts)
        return (
            test_result,
            merge_fingerprint,
            left_fingreprint,
            right_fingerprint,
            run_time,
        )

    def merge_and_test_cached(  # pylint: disable=too-many-arguments
        self,
        tool: MERGE_TOOL,
        left_commit: str,
        right_commit: str,
        timeout: int,
        n_restarts: int,
    ) -> Tuple[
        Union[TEST_STATE, MERGE_STATE],
        Union[str, None],
        Union[str, None],
        Union[str, None],
        float,
    ]:
        """Merges the given commits using the given tool and tests the result.
        Args:
            tool (MERGE_TOOL): The tool to use.
            left_commit (str): The left commit to merge.
            right_commit (str): The right commit to merge.
            timeout (int): The timeout limit.
            n_restarts (int): The number of times to restart the test.
        Returns:
            TEST_STATE: The result of the test.
            str: The tree fingerprint of result.
            str: The left fingerprint.
            str: The right fingerprint.
            float: The time it took to run the merge.
        """
        sha_cache = self.check_sha_cache(
            left_commit + "_" + right_commit + "_" + tool.name
        )
        if sha_cache is None:
            return self.merge_and_test(
                tool, left_commit, right_commit, timeout, n_restarts
            )
        if sha_cache["sha"] is None:
            return TEST_STATE.Git_checkout_failed, None, None, None, -1
        result = self.check_test_cache(sha_cache["sha"])
        if result is None:
            return self.merge_and_test(
                tool, left_commit, right_commit, timeout, n_restarts
            )
        return (
            result,
            sha_cache["sha"],
            sha_cache["left_fingerprint"],
            sha_cache["right_fingerprint"],
            -1,
        )

    def merge(  # pylint: disable=too-many-locals
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
            explanation (str): The explanation of the result.
            timeout (int): The timeout limit.
        Returns:
            MERGE_STATE: The result of the merge.
            str: The tree fingerprint of result.
            str: The left fingerprint.
            str: The right fingerprint.
            str: explanation. The explanation of the result.
            float: The time it took to run the merge.
        """
        # Checkout left
        cache_name = left_commit + "_" + right_commit + "_" + tool.name
        left_cache = self.check_sha_cache(left_commit)
        if left_cache is not None and left_cache["sha"] is None:
            return (
                MERGE_STATE.Git_checkout_failed,
                None,
                None,
                None,
                left_cache["explanation"],
                -1,
            )
        success, explanation = self.checkout(left_commit)
        if not success:
            set_in_cache(
                left_commit,
                {"sha": None, "explanation": explanation},
                self.repo_name,
                self.sha_cache_prefix,
            )
            set_in_cache(
                cache_name,
                {"sha": None, "explanation": explanation},
                self.repo_name,
                self.sha_cache_prefix,
            )
            return MERGE_STATE.Git_checkout_failed, None, None, None, explanation, -1
        left_fingreprint = self.compute_tree_fingerprint()
        self.repo.git.checkout("-b", LEFT_BRANCH_NAME, force=True)

        # Checkout right
        right_cache = self.check_sha_cache(right_commit)
        if right_cache is not None and right_cache["sha"] is None:
            return (
                MERGE_STATE.Git_checkout_failed,
                None,
                None,
                None,
                right_cache["explanation"],
                -1,
            )
        success, explanation = self.checkout(right_commit)
        if not success:
            set_in_cache(
                right_commit,
                {"sha": None, "explanation": explanation},
                self.repo_name,
                self.sha_cache_prefix,
            )
            set_in_cache(
                cache_name,
                {"sha": None, "explanation": explanation},
                self.repo_name,
                self.sha_cache_prefix,
            )
            return MERGE_STATE.Git_checkout_failed, None, None, None, explanation, -1
        right_fingerprint = self.compute_tree_fingerprint()
        self.repo.git.checkout("-b", RIGHT_BRANCH_NAME, force=True)

        # Merge
        start = time.time()
        try:
            command = [
                "src/scripts/merge_tools/" + tool.name.replace("_", "-") + ".sh",
                str(self.repo_path),
                LEFT_BRANCH_NAME,
                RIGHT_BRANCH_NAME,
            ]
            p = subprocess.run(  # pylint: disable=consider-using-with
                command,
                capture_output=True,
                timeout=timeout if timeout > 0 else None,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            explanation = "Run Command: " + " ".join(command) + "\nTimed out"  # type: ignore
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
        cache_entry = {
            "sha": sha,
            "left_fingerprint": left_fingreprint,
            "right_fingerprint": right_fingerprint,
        }
        set_in_cache(
            cache_name,
            cache_entry,
            self.repo_name,
            self.sha_cache_prefix,
        )
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
            "sha256sum <(export LC_COLLATE=C; cd "
            + str(self.repo_path)
            + " ;find . -type f -not -path '*/\\.git*' -exec sha256sum {} \\; | sort)"
        )
        result = (
            subprocess.check_output(command, shell=True, executable="/bin/bash")
            .decode("utf-8")
            .split()[0]
        )
        return result

    def check_sha_cache(
        self, commit: str, start_merge: bool = False
    ) -> Union[None, dict]:
        """Checks if the commit is in the cache.
        Args:
            commit (str): The commit to check.
            start_merge (bool, optional) = False: Whether to indicate that the merge starts if the
                commit is not in the cache.
        Returns:
            Union[None,dict]: The cache entry if the commit is in the cache, None otherwise.
        """
        cache = check_and_load_cache(
            commit, self.repo_name, self.sha_cache_prefix, set_run=start_merge
        )
        if cache is None:
            return None
        if not isinstance(cache, dict):
            raise Exception("Cache entry should be a dictionary")
        return cache

    def check_test_cache(
        self, sha: str, start_test: bool = False
    ) -> Union[None, TEST_STATE]:
        """Checks if the test entry is in the cache.
        Args:
            sha (str): The tree fingerprint of the repository.
            start_test (bool, optional) = False: Whether to indicate that the test starts if the
                entry is not in the cache.
        Returns:
            Union[None,TEST_STATE]: The result of the test if the repository is in the cache,
                    None otherwise.
        """
        cache = check_and_load_cache(
            sha, self.repo_name, self.test_cache_prefix, set_run=start_test
        )
        if cache is None:
            return None
        if not isinstance(cache, dict):
            raise Exception("Cache entry should be a dictionary")
        return TEST_STATE[cache["test_result"]]

    def checkout_and_test(
        self,
        commit: str,
        timeout: int,
        n_restarts: int,
    ) -> TEST_STATE:
        """Checks out the given commit and tests the repository.
        Args:
            commit (str): The commit to checkout.
            timeout (int): The timeout limit.
            n_restarts (int): The number of times to restart the test.
        Returns:
            TEST_STATE: The result of the test.
        """
        result, explanation = self.checkout(commit)
        if not result:
            print("Checkout failed for", self.repo_name, commit, explanation)
            return TEST_STATE.Git_checkout_failed
        return self.test(timeout, n_restarts)

    def checkout_and_test_cached(
        self,
        commit: str,
        timeout: int,
        n_restarts: int,
    ) -> TEST_STATE:
        """Checks out the given commit and tests the repository.
        Args:
            commit (str): The commit to checkout.
            timeout (int): The timeout limit.
            n_restarts (int): The number of times to restart the test.
            check_cache (bool, optional) = True: Whether to check the cache.
        Returns:
            TEST_STATE: The result of the test.
        """
        sha_cache = self.check_sha_cache(commit, start_merge=True)
        if sha_cache is None:
            return self.checkout_and_test(commit, timeout, n_restarts)
        if sha_cache["sha"] is None:
            return TEST_STATE.Git_checkout_failed
        result = self.check_test_cache(sha_cache["sha"])
        if result is None:
            return self.checkout_and_test(commit, timeout, n_restarts)
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
        cache_data = {}

        result = self.check_test_cache(sha, start_test=True)
        if result is not None:
            return result

        cache_data["test_results"] = []
        cache_data["test_log_file"] = []
        for i in range(n_restarts):
            test, explanation = repo_test(self.repo_path, timeout)
            test_log_file = Path(
                os.path.join(
                    self.test_cache_prefix,
                    "logs",
                    self.repo_name.split("/")[1],
                    sha + "_" + str(i) + ".log",
                )
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

        set_in_cache(sha, cache_data, self.repo_name, self.test_cache_prefix)
        return TEST_STATE[cache_data["test_result"]]

    def __del__(self) -> None:
        """Deletes the repository."""
        if DELETE_WORKDIRS:
            shutil.rmtree(self.workdir)
