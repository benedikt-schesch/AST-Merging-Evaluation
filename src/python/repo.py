#!/usr/bin/env python3
"""
This script contains the Repository class that represents a repository.
It also contains the functions that are used to test the repository.
"""

from pathlib import Path
from typing import Union, Tuple, List
from enum import Enum
import uuid
import subprocess
import os
import shutil
import time
from git.repo import Repo
from cache_utils import (
    set_in_cache,
    lookup_in_cache,
    slug_repo_name,
)
from variables import *

TEST_STATE = Enum(
    "TEST_STATE",
    [
        "Tests_passed",
        "Tests_failed",
        "Tests_timedout",
        "Git_checkout_failed",
        "Not_tested",
    ],
)
MERGE_TOOL = Enum(
    "MERGE_TOOL",
    [
        "gitmerge_ort",
        "gitmerge_ort_ignorespace",
        "gitmerge_recursive_ignorespace",
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


def compute_explanation(
    command: List[str],
    source: Union[subprocess.TimeoutExpired, subprocess.CompletedProcess],
) -> str:
    """Poduces the explanation string of a timedout process or
    a completed process.
    """
    explanation = "Run Command: " + " ".join(command) + "\nTimed out"
    explanation += (
        "\nstdout:\n" + source.stdout.decode("utf-8") if source.stdout else ""
    )
    explanation += (
        "\nstderr:\n" + source.stderr.decode("utf-8") if source.stderr else ""
    )
    return explanation


def repo_test(wcopy_dir: Path, timeout: int) -> Tuple[TEST_STATE, str]:
    """Returns the result of run_repo_tests.sh on the given working copy.
    If the test process passes then the entire test is marked as passed.
    If the test process timeouts then the entire test is marked as timeout.
    Args:
        wcopy_dir (Path): The path of the working copy (the clone).
        timeout (int): Test timeout limit, in seconds.
    Returns:
        TEST_STATE: The result of the test.
        str: explanation. The explanation of the result.
    """
    explanation = ""
    command = [
        "src/scripts/run_repo_tests.sh",
        str(wcopy_dir),
    ]
    try:
        p = subprocess.run(  # pylint: disable=consider-using-with
            command,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        explanation = compute_explanation(command, e)
        return TEST_STATE.Tests_timedout, explanation
    rc = p.returncode
    explanation = compute_explanation(command, p)
    if rc == 0:  # Success
        return TEST_STATE.Tests_passed, explanation
    return TEST_STATE.Tests_failed, explanation


class Repository:
    """A class that represents a repository."""

    def __init__(
        self,
        repo_slug: str,
        cache_prefix: Path = Path(""),
    ) -> None:
        """Initializes the repository.
        Args:
            repo_slug (str): The slug of the repository, which is "owner/reponame".
            cache_prefix (Path): The prefix of the cache.
        """
        self.repo_slug = repo_slug
        self.path = REPOS_PATH / repo_slug.split("/")[1]
        workdir_id = uuid.uuid4().hex
        self.workdir = WORKDIR_PREFIX / workdir_id
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.repo_path = self.workdir / self.path.name
        shutil.copytree(self.path, self.repo_path)
        self.repo = Repo(self.repo_path)
        self.test_cache_prefix = cache_prefix / "test_cache"
        self.sha_cache_prefix = cache_prefix / "sha_cache_entry"

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
            explanation = f"Checked out {commit} for {self.repo_slug}"
            self.repo.submodule_update()
        except Exception as e:
            explanation = (
                "Failed to checkout "
                + commit
                + " for "
                + self.repo_slug
                + " : \n"
                + str(e)
            )
            cache_entry = {"sha": None, "explanation": explanation}
            set_in_cache(commit, cache_entry, self.repo_slug, self.sha_cache_prefix)
            return False, explanation
        cache_entry = {
            "sha": self.compute_tree_fingerprint(),
            "explanation": explanation,
        }
        set_in_cache(commit, cache_entry, self.repo_slug, self.sha_cache_prefix)
        return True, explanation

    def _merge_and_test(  # pylint: disable=too-many-arguments
        self,
        tool: MERGE_TOOL,
        left_commit: str,
        right_commit: str,
        timeout: int,  # in seconds
        n_tests: int,
    ) -> Tuple[
        Union[TEST_STATE, MERGE_STATE],
        Union[str, None],
        Union[str, None],
        Union[str, None],
        float,
    ]:
        """Merges the given commits using the given tool and tests the result.
        The test results of multiple runs is combined into one result.
        Args:
            tool (MERGE_TOOL): The tool to use.
            left_commit (str): The left commit to merge.
            right_commit (str): The right commit to merge.
            timeout (int): The timeout limit, in seconds.
            n_tests (int): The number of times to perform the test.
        Returns:
            TEST_STATE: The result of the test.
            str: The tree fingerprint of the merge result.
            str: The left fingerprint.
            str: The right fingerprint.
            float: The time it took to run the merge, in seconds.
        """
        (
            merge_status,
            merge_fingerprint,
            left_fingerprint,
            right_fingerprint,
            _,
            run_time,
        ) = self.merge(tool, left_commit, right_commit, -1)
        if merge_status != MERGE_STATE.Merge_success:
            return merge_status, None, None, None, -1
        test_result = self.test(timeout, n_tests)
        return (
            test_result,
            merge_fingerprint,
            left_fingerprint,
            right_fingerprint,
            run_time,
        )

    def merge_and_test(  # pylint: disable=too-many-arguments
        self,
        tool: MERGE_TOOL,
        left_commit: str,
        right_commit: str,
        timeout: int,
        n_tests: int,
    ) -> Tuple[
        Union[TEST_STATE, MERGE_STATE],
        Union[str, None],
        Union[str, None],
        Union[str, None],
        float,
    ]:
        """Merges the given commits using the given tool and tests the result.
        The test results of multiple runs is combined into one result.
        Args:
            tool (MERGE_TOOL): The tool to use.
            left_commit (str): The left commit to merge.
            right_commit (str): The right commit to merge.
            timeout (int): The timeout limit, in seconds.
            n_tests (int): The number of times to run the test.
        Returns:
            TEST_STATE: The result of the test.
            str: The tree fingerprint of the result.
            str: The left fingerprint.
            str: The right fingerprint.
            float: The time it took to run the merge, in seconds.
        """
        sha_cache_entry = self.get_sha_cache_entry(
            left_commit + "_" + right_commit + "_" + tool.name
        )
        if sha_cache_entry is None:
            return self._merge_and_test(
                tool, left_commit, right_commit, timeout, n_tests
            )
        if sha_cache_entry["sha"] is None:
            return TEST_STATE.Git_checkout_failed, None, None, None, -1
        result = self.get_test_cache_entry(sha_cache_entry["sha"])
        if result is None:
            return self._merge_and_test(
                tool, left_commit, right_commit, timeout, n_tests
            )
        return (
            result,
            sha_cache_entry["sha"],
            sha_cache_entry["left_fingerprint"],
            sha_cache_entry["right_fingerprint"],
            -1,
        )

    def create_branch(
        self, branch_name: str, commit: str
    ) -> Tuple[Union[None, str], str]:
        """Creates a branch from a certain commit.
        Args:
            branch_name (str): Name of the branch to create.
            commit (str): Commit used to create the branch.
        Returns:
            Union[None,str] : None if a checkout failure occured,
                    str is the fingerprint of that commit.
            str: explanation of the result.
        """
        cache_entry = self.get_sha_cache_entry(commit)
        if cache_entry is not None and cache_entry["sha"] is None:
            return None, cache_entry["explanation"]
        success, explanation = self.checkout(commit)
        if not success:
            set_in_cache(
                commit,
                {"sha": None, "explanation": explanation},
                self.repo_slug,
                self.sha_cache_prefix,
            )
            return None, explanation
        tree_fingerprint = self.compute_tree_fingerprint()
        self.repo.git.checkout("-b", branch_name, force=True)
        return tree_fingerprint, explanation

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
            timeout (int): The timeout limit, in seconds.
        Returns:
            MERGE_STATE: The result of the merge.
            str: The tree fingerprint of the result.
            str: The left fingerprint.
            str: The right fingerprint.
            str: explanation. The explanation of the result.
            float: The time it took to run the merge, in seconds.
        """
        cache_entry_name = left_commit + "_" + right_commit + "_" + tool.name

        # Checkout left
        left_fingerprint, left_explanation = self.create_branch(
            LEFT_BRANCH_NAME, left_commit
        )

        # Checkout right
        right_fingerprint, right_explanation = self.create_branch(
            RIGHT_BRANCH_NAME, right_commit
        )
        explanation = left_explanation + "\n" + right_explanation
        if right_fingerprint is None or left_fingerprint is None:
            set_in_cache(
                cache_entry_name,
                {"sha": None, "explanation": explanation},
                self.repo_slug,
                self.sha_cache_prefix,
            )
            return (
                MERGE_STATE.Git_checkout_failed,
                None,
                None,
                None,
                explanation,
                -1,
            )

        # Merge
        start_time = time.time()
        command = [
            "src/scripts/merge_tools/" + tool.name + ".sh",
            str(self.repo_path),
            LEFT_BRANCH_NAME,
            RIGHT_BRANCH_NAME,
        ]
        try:
            p = subprocess.run(  # pylint: disable=consider-using-with
                command,
                capture_output=True,
                timeout=timeout if timeout > 0 else None,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            explanation = explanation + "\n" + compute_explanation(command, e)
            sha = self.compute_tree_fingerprint()
            return (
                MERGE_STATE.Merge_timedout,
                sha,
                left_fingerprint,
                right_fingerprint,
                explanation,
                -1,
            )
        run_time = time.time() - start_time
        explanation = explanation + "\n" + compute_explanation(command, p)
        merge_status = (
            MERGE_STATE.Merge_success if p.returncode == 0 else MERGE_STATE.Merge_failed
        )
        sha = self.compute_tree_fingerprint()
        cache_entry = {
            "sha": sha,
            "left_fingerprint": left_fingerprint,
            "right_fingerprint": right_fingerprint,
        }
        set_in_cache(
            cache_entry_name,
            cache_entry,
            self.repo_slug,
            self.sha_cache_prefix,
        )
        return (
            merge_status,
            sha,
            left_fingerprint,
            right_fingerprint,
            explanation,
            run_time,
        )

    def compute_tree_fingerprint(self) -> str:
        """Computes the tree fingerprint of the repository.
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

    def get_sha_cache_entry(
        self, commit: str, start_merge: bool = False
    ) -> Union[None, dict]:
        """Gets a SHA cache entry.
        Args:
            commit (str): The commit to check.
            start_merge (bool, optional) = False: Whether to indicate that the merge starts if the
                commit is not in the cache.
        Returns:
            Union[None,dict]: The cache entry if the commit is in the cache, None otherwise.
        """
        cache = lookup_in_cache(
            commit, self.repo_slug, self.sha_cache_prefix, set_run=start_merge
        )
        if cache is None:
            return None
        if not isinstance(cache, dict):
            raise Exception("Cache entry should be a dictionary")
        return cache

    def get_test_cache_entry(
        self, sha: str, start_test: bool = False
    ) -> Union[None, TEST_STATE]:
        """Gets a test cache entry.
        Args:
            sha (str): The tree fingerprint of the repository.
            start_test (bool, optional) = False: Whether to indicate that the test starts if the
                entry is not in the cache.
        Returns:
            Union[None,TEST_STATE]: The result of the test if the repository is in the cache,
                    None otherwise.
        """
        cache = lookup_in_cache(
            sha, self.repo_slug, self.test_cache_prefix, set_run=start_test
        )
        if cache is None:
            return None
        if not isinstance(cache, dict):
            raise Exception("Cache entry should be a dictionary")
        return TEST_STATE[cache["test_result"]]

    def _checkout_and_test(
        self,
        commit: str,
        timeout: int,
        n_tests: int,
    ) -> TEST_STATE:
        """Checks out the given commit and tests the repository.
        Args:
            commit (str): The commit to checkout.
            timeout (int): The timeout limit, in seconds.
            n_tests (int): The number of times to run the test suite.
        Returns:
            TEST_STATE: The result of the test.
        """
        result, explanation = self.checkout(commit)
        if not result:
            print("Checkout failed for", self.repo_slug, commit, explanation)
            return TEST_STATE.Git_checkout_failed
        return self.test(timeout, n_tests)

    def checkout_and_test(
        self,
        commit: str,
        timeout: int,
        n_tests: int,
    ) -> TEST_STATE:
        """Checks out the given commit and tests the repository.
        Args:
            commit (str): The commit to checkout.
            timeout (int): The timeout limit, in seconds.
            n_tests (int): The number of times to run the test suite.
            check_cache (bool, optional) = True: Whether to check the cache.
        Returns:
            TEST_STATE: The result of the test.
        """
        sha_cache_entry = self.get_sha_cache_entry(commit, start_merge=True)
        if sha_cache_entry is None:
            return self._checkout_and_test(commit, timeout, n_tests)
        if sha_cache_entry["sha"] is None:
            return TEST_STATE.Git_checkout_failed
        result = self.get_test_cache_entry(sha_cache_entry["sha"])
        if result is None:
            return self._checkout_and_test(commit, timeout, n_tests)
        return result

    def test(self, timeout: int, n_tests: int) -> TEST_STATE:
        """Tests the repository. The test results of multiple runs is combined into one result.
        If one of the runs passes then the entire test is marked as passed.
        If one of the runs timeouts then the entire test is marked as timeout.
        Args:
            timeout (int): The timeout limit, in seconds.
            n_tests (int): The number of times to run the test suite.
        Returns:
            TEST_STATE: The result of the test.
        """
        sha = self.compute_tree_fingerprint()
        cache_data = {}

        result = self.get_test_cache_entry(sha, start_test=True)
        if result is not None:
            return result

        cache_data["test_results"] = []
        cache_data["test_log_file"] = []
        for i in range(n_tests):
            test_state, test_output = repo_test(self.repo_path, timeout)
            test_log_file = Path(
                os.path.join(
                    self.test_cache_prefix,
                    "logs",
                    slug_repo_name(self.repo_slug),
                    sha + "_" + str(i) + ".log",
                )
            )
            test_log_file.parent.mkdir(parents=True, exist_ok=True)
            if test_log_file.exists():
                test_log_file.unlink()
            with open(test_log_file, "w") as f:
                f.write(test_output)
            cache_data["test_results"].append(test_state.name)
            cache_data["test_log_file"].append(str(test_log_file))
            cache_data["test_result"] = test_state.name
            if test_state in (TEST_STATE.Tests_passed, TEST_STATE.Tests_timedout):
                break

        set_in_cache(sha, cache_data, self.repo_slug, self.test_cache_prefix)
        return TEST_STATE[cache_data["test_result"]]

    def __del__(self) -> None:
        """Deletes the repository."""
        if DELETE_WORKDIRS:
            shutil.rmtree(self.workdir)
