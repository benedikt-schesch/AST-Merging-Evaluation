#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script contains the Repository class that represents a repository.
It also contains the functions that are used to test the repository.
"""

from pathlib import Path
from typing import Union, Tuple, List, Dict
import errno
import signal
import functools
from enum import Enum
import uuid
import subprocess
import os
import xml.etree.ElementTree as ET
import shutil
import time
from git.repo import Repo
from git import GitCommandError
from cache_utils import (
    set_in_cache,
    lookup_in_cache,
)
import fasteners
import git.repo
from variables import (
    REPOS_PATH,
    WORKDIR_DIRECTORY,
    LEFT_BRANCH_NAME,
    RIGHT_BRANCH_NAME,
    DELETE_WORKDIRS,
    N_TESTS,
    TIMEOUT_MERGING,
)
from loguru import logger


def timeout(seconds=10, error_message=os.strerror(errno.ETIME)):
    """A decorator that raises a TimeoutError if a function takes too long to run."""

    def decorator(func):
        def _handle_timeout(signum, frame):
            raise Exception(error_message)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wrapper

    return decorator


@timeout(10 * 60)
def clone_repo(repo_slug: str, repo_dir: Path) -> None:
    """Clones a repository, or runs `git fetch` if the repository is already cloned.
    Args:
        repo_slug (str): The slug of the repository, which is "owner/reponame".
    """
    logger.debug(f"clone_repo: Cloning {repo_slug} to {repo_dir}")
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    os.environ["GIT_TERMINAL_PROMPT"] = "0"
    os.environ["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
    # ":@" in URL ensures that we are not prompted for login details
    # for the repos that are now private.
    github_url = "https://:@github.com/" + repo_slug + ".git"
    try:
        repo = git.repo.Repo.clone_from(github_url, repo_dir)
        assert (
            repo_dir.exists()
        ), f"Repo {repo_slug} does not exist after cloning {repo_dir}"
        logger.debug(repo_slug, "clone_repo: Finished cloning")
        repo.remote().fetch()
        repo.remote().fetch("refs/pull/*/head:refs/remotes/origin/pull/*")
    except GitCommandError as e:
        logger.debug(f"clone_repo: GitCommandError during cloning {repo_slug}:\n{e}")
        raise Exception(f"GitCommandError during cloning {repo_slug}") from e
    try:
        repo.submodule_update()
    except ValueError as e:
        logger.debug(
            f"clone_repo: ValueError during submodule update {repo_slug}:\n{e}"
        )
    if not repo_dir.exists():
        logger.error(f"Repo {repo_slug} does not exist after cloning {repo_dir}")
        raise Exception(
            f"Repo {repo_slug} does not exist after cloning {repo_dir}"
        ) from None


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
        "gitmerge_recursive_histogram",
        "gitmerge_recursive_ignorespace",
        "gitmerge_recursive_minimal",
        "gitmerge_recursive_myers",
        "gitmerge_recursive_patience",
        "gitmerge_resolve",
        "git_hires_merge",
        "spork",
        "intellimerge",
        "adjacent",
        "imports",
        "version_numbers",
        "git_hires_merge_plus",
        "intellimerge_plus",
        "gitmerge_recursive_histogram_plus",
        "gitmerge_recursive_ignorespace_plus",
        "gitmerge_recursive_minimal_plus",
        "gitmerge_recursive_myers_plus",
        "gitmerge_recursive_patience_plus",
        "gitmerge_resolve_plus",
        "spork_plus",
        "ivn",
        "ivn_ignorespace",
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


def stdout_and_stderr(
    command: List[str],
    source: Union[subprocess.TimeoutExpired, subprocess.CompletedProcess],
) -> str:
    """Produces the standard output and standard error of a timedout process."""
    explanation = "Run Command: " + " ".join(command) + "\nTimed out"
    if source.stdout:
        explanation += "\nstdout:\n" + source.stdout.decode("utf-8", "replace")
    if source.stderr:
        explanation += "\nstderr:\n" + source.stderr.decode("utf-8", "replace")
    return explanation


def repo_test(wcopy_dir: Path, timeout: int) -> Tuple[TEST_STATE, str]:
    """Returns the result of run_repo_tests.sh on the given working copy.
    If the test process passes then the function returns and marks it as passed.
    If the test process timeouts then the function returns and marks it as timedout.
    Args:
        wcopy_dir (Path): The directory of the working copy (the clone).
        timeout (int): Test timeout limit, in seconds.
    Returns:
        TEST_STATE: The result of the test.
        str: explanation. The explanation of the result.
    """
    explanation = ""
    command = [
        "src/scripts/run_with_timeout.sh",
        str(timeout),
        f"src/scripts/run_repo_tests.sh {wcopy_dir}",
    ]
    p = subprocess.run(
        command,
        capture_output=True,
    )
    if p.returncode == 124:  # Timeout
        explanation = stdout_and_stderr(command, p)
        return TEST_STATE.Tests_timedout, explanation
    explanation = stdout_and_stderr(command, p)
    if p.returncode == 0:  # Success
        return TEST_STATE.Tests_passed, explanation
    return TEST_STATE.Tests_failed, explanation


class Repository:
    """A class that represents a repository.
    merge_idx is purely for diagnostic purposes.
    """

    merge_idx: str
    repo_slug: str
    owner: str
    name: str
    repo_path: Path
    workdir: Path
    local_repo_path: Path
    delete_workdir: bool
    lazy_clone: bool
    repo: Repo
    test_cache_directory: Path
    sha_cache_directory: Path

    def __init__(
        self,
        merge_idx: str,
        repo_slug: str,
        cache_directory: Path = Path(""),
        workdir_id: str = uuid.uuid4().hex,  # uuid4 is a random UID
        delete_workdir: bool = DELETE_WORKDIRS,
        lazy_clone: bool = False,
    ) -> None:
        """Initializes the repository.
        Args:
            repo_slug (str): The slug of the repository, which is "owner/reponame".
            cache_directory (Path): The prefix of the cache.
        """
        self.merge_idx = merge_idx
        self.repo_slug = repo_slug.lower()
        self.owner, self.name = self.repo_slug.split("/")
        self.repo_path = REPOS_PATH / repo_slug
        self.workdir = WORKDIR_DIRECTORY / workdir_id
        self.local_repo_path = self.workdir / self.repo_path.name
        self.delete_workdir = delete_workdir
        self.lazy_clone = lazy_clone
        if not lazy_clone:
            self.clone_repo()
            self.copy_repo()
        self.test_cache_directory = cache_directory / "test_cache"
        self.sha_cache_directory = cache_directory / "sha_cache_entry"

    def clone_repo(self) -> None:
        """Clones the repository."""
        lock_path = REPOS_PATH / "locks" / self.repo_slug
        lock = fasteners.InterProcessLock(lock_path)
        with lock:
            if self.repo_path.exists():
                return
            try:
                clone_repo(self.repo_slug, self.repo_path)
            except Exception as e:
                logger.error("Exception during cloning:\n", e)
                raise
        if not self.repo_path.exists():
            logger.error(
                f"Repo {self.repo_slug} does not exist after cloning {self.repo_path}"
            )
            raise Exception(
                f"Repo {self.repo_slug} does not exist after cloning {self.repo_path}"
            )

    def copy_repo(self) -> None:
        """Copies the repository and adjusts permissions."""
        if not self.repo_path.exists():
            self.clone_repo()
        if self.local_repo_path.exists():
            shutil.rmtree(self.local_repo_path, ignore_errors=True)
        self.workdir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            self.repo_path,
            self.local_repo_path,
            symlinks=True,
            ignore_dangling_symlinks=True,
        )
        os.system("chmod -R 777 " + str(self.local_repo_path))
        self.repo = Repo(self.local_repo_path)

    def checkout(self, commit: str, use_cache: bool = True) -> Tuple[bool, str]:
        """Checks out the given commit.
        Args:
            commit (str): The commit to checkout.
            use_cache (bool, optional) = True: Whether to check the cache.
        Returns:
            bool: True if the checkout succeeded, False otherwise.
            str: explanation. The explanation of the result.
        """
        if not self.repo_path.exists():
            try:
                self.clone_repo()
            except Exception as e:
                if use_cache:
                    cache_entry = {"sha": None, "explanation": str(e)}
                    set_in_cache(
                        commit, cache_entry, self.repo_slug, self.sha_cache_directory
                    )
                return False, "Failed to clone " + self.repo_slug + " : \n" + str(e)
        assert self.repo_path.exists(), f"Repo {self.repo_slug} does not exist"
        if not self.local_repo_path.exists():
            self.copy_repo()
        assert self.local_repo_path.exists()
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
            if use_cache:
                cache_entry = {"sha": None, "explanation": explanation}
                set_in_cache(
                    commit, cache_entry, self.repo_slug, self.sha_cache_directory
                )
            return False, explanation
        if use_cache:
            cache_entry = {
                "sha": self.compute_tree_fingerprint(),
                "explanation": explanation,
            }
            set_in_cache(commit, cache_entry, self.repo_slug, self.sha_cache_directory)
        return True, explanation

    def _merge_and_test(
        self,
        tool: MERGE_TOOL,
        left_commit: str,
        right_commit: str,
        timeout_test: int,
        timeout_merge: int = TIMEOUT_MERGING,
        n_tests: int = N_TESTS,
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
            timeout_test (int): The timeout limit for the test, in seconds.
            timeout_merge (int): The timeout limit for the merge, in seconds.
            n_tests (int): The number of times to run the test.
        Returns:
            TEST_STATE: The result of the test.
            str: The tree fingerprint of the merge result.
            str: The left fingerprint.
            str: The right fingerprint.
            float: The test coverage.
        """
        (
            merge_status,
            merge_fingerprint,
            left_fingerprint,
            right_fingerprint,
            _,
            _,
        ) = self.merge(tool, left_commit, right_commit, timeout_merge)
        if merge_status != MERGE_STATE.Merge_success:
            return (
                merge_status,
                merge_fingerprint,
                left_fingerprint,
                right_fingerprint,
                -1,
            )
        test_result, test_coverage = self.test(timeout_test, n_tests)
        return (
            test_result,
            merge_fingerprint,
            left_fingerprint,
            right_fingerprint,
            test_coverage,
        )

    def merge_and_test(
        self,
        tool: MERGE_TOOL,
        left_commit: str,
        right_commit: str,
        timeout_test: int,
        timeout_merge: int = TIMEOUT_MERGING,
        n_tests: int = N_TESTS,
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
            timeout_test (int): The timeout limit for the test, in seconds.
            timeout_merge (int): The timeout limit for the merge, in seconds.
            n_tests (int): The number of times to run the test.
        Returns:
            TEST_STATE: The result of the test.
            str: The tree fingerprint of the result.
            str: The left fingerprint.
            str: The right fingerprint.
            float: The test coverage.
        """
        sha_cache_entry = self.get_sha_cache_entry(
            left_commit + "_" + right_commit + "_" + tool.name
        )
        if sha_cache_entry is None:
            return self._merge_and_test(
                tool=tool,
                left_commit=left_commit,
                right_commit=right_commit,
                timeout_test=timeout_test,
                timeout_merge=timeout_merge,
                n_tests=n_tests,
            )
        merge_result = MERGE_STATE[sha_cache_entry["merge status"]]
        if merge_result != MERGE_STATE.Merge_success:
            return (
                merge_result,
                sha_cache_entry["sha"],
                sha_cache_entry["left_fingerprint"],
                sha_cache_entry["right_fingerprint"],
                -1,
            )
        result, test_coverage = self.get_test_cache_entry(sha_cache_entry["sha"])
        if result is None:
            return self._merge_and_test(
                tool=tool,
                left_commit=left_commit,
                right_commit=right_commit,
                timeout_test=timeout_test,
                timeout_merge=timeout_merge,
                n_tests=n_tests,
            )
        return (
            result,
            sha_cache_entry["sha"],
            sha_cache_entry["left_fingerprint"],
            sha_cache_entry["right_fingerprint"],
            test_coverage,
        )

    def create_branch(
        self, branch_name: str, commit: str, use_cache: bool = True
    ) -> Tuple[Union[None, str], str]:
        """Creates a branch from a certain commit.
        Args:
            branch_name (str): Name of the branch to create.
            commit (str): Commit used to create the branch.
            use_cache (bool, optional) = True: Whether to check the cache.
        Returns:
            Union[None,str] : None if a checkout failure occured,
                    str is the fingerprint of that commit.
            str: explanation of the result.
        """
        if use_cache:
            cache_entry = self.get_sha_cache_entry(commit)
            if cache_entry is not None and cache_entry["sha"] is None:
                return None, cache_entry["explanation"]
        success, explanation = self.checkout(commit, use_cache=use_cache)
        assert self.local_repo_path.exists(), f"Repo {self.repo_slug} does not exist"
        if not success:
            if use_cache:
                set_in_cache(
                    commit,
                    {"sha": None, "explanation": explanation},
                    self.repo_slug,
                    self.sha_cache_directory,
                )
            return None, explanation
        tree_fingerprint = self.compute_tree_fingerprint()
        self.repo.git.checkout("-b", branch_name, force=True)
        return tree_fingerprint, explanation

    def merge(
        self,
        tool: MERGE_TOOL,
        left_commit: str,
        right_commit: str,
        timeout: int,
        use_cache: bool = True,
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
            use_cache (bool, optional) = True: Whether to check the cache.
        Returns:
            MERGE_STATE: The result of the merge.
            str: The tree fingerprint of the result.
            str: The left fingerprint.
            str: The right fingerprint.
            str: explanation. The explanation of the result.
            float: The time it took to run the merge, in seconds.
        """
        cache_entry_name = left_commit + "_" + right_commit + "_" + tool.name
        cache_entry: Dict[str, Union[str, None]] = {"sha": None}
        # Checkout left
        left_fingerprint, left_explanation = self.create_branch(
            LEFT_BRANCH_NAME, left_commit, use_cache=use_cache
        )
        cache_entry["left_fingerprint"] = left_fingerprint

        # Checkout right
        right_fingerprint, right_explanation = self.create_branch(
            RIGHT_BRANCH_NAME, right_commit, use_cache=use_cache
        )
        cache_entry["right_fingerprint"] = right_fingerprint
        explanation = left_explanation + "\n" + right_explanation
        if right_fingerprint is None or left_fingerprint is None:
            if use_cache:
                cache_entry["merge status"] = MERGE_STATE.Git_checkout_failed.name
                cache_entry["explanation"] = explanation
                set_in_cache(
                    cache_entry_name,
                    cache_entry,
                    self.repo_slug,
                    self.sha_cache_directory,
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
        logger.debug(
            f"merge: Merging {self.repo_slug} {left_commit} {right_commit} with {tool.name}"
        )
        start_time = time.time()
        command = [
            "src/scripts/run_with_timeout.sh",
            str(timeout),
            f"src/scripts/merge_tools/{tool.name}.sh {self.local_repo_path.resolve()} {LEFT_BRANCH_NAME} {RIGHT_BRANCH_NAME}",
        ]
        p = subprocess.run(
            command,
            capture_output=True,
            check=False,
        )
        if p.returncode == 124:  # Timeout
            explanation = explanation + "\n" + stdout_and_stderr(command, p)
            if use_cache:
                cache_entry["merge status"] = MERGE_STATE.Merge_timedout.name
                cache_entry["explanation"] = explanation
                set_in_cache(
                    cache_entry_name,
                    cache_entry,
                    self.repo_slug,
                    self.sha_cache_directory,
                )
            return (
                MERGE_STATE.Merge_timedout,
                None,
                left_fingerprint,
                right_fingerprint,
                explanation,
                -1,
            )
        run_time = time.time() - start_time
        explanation = explanation + "\n" + stdout_and_stderr(command, p)
        merge_status = (
            MERGE_STATE.Merge_success if p.returncode == 0 else MERGE_STATE.Merge_failed
        )
        sha = self.compute_tree_fingerprint()
        if use_cache:
            cache_entry["sha"] = sha
            cache_entry["merge status"] = merge_status.name
            output_file = (
                self.sha_cache_directory
                / self.owner
                / "logs"
                / f"{cache_entry_name}.log"
            )
            output_file.parent.mkdir(parents=True, exist_ok=True)
            cache_entry["merge_logs"] = str(output_file)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(explanation)
            set_in_cache(
                cache_entry_name,
                cache_entry,
                self.repo_slug,
                self.sha_cache_directory,
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
        This function must never be run after running tests,
        since running tests might write output files.
        Returns:
            str: The tree fingerprint.
        """
        assert self.local_repo_path.exists(), f"Repo {self.repo_slug} does not exist"
        command = (
            "sha256sum <(export LC_ALL=C; export LC_COLLATE=C; cd "
            + str(self.local_repo_path)
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
        """The SHA cache maps a commit to a tree fingerprint.
        This function checks if the commit is in the cache.
        Args:
            commit (str): The commit to check.
            start_merge (bool, optional) = False: Whether to indicate that the merge starts if the
                commit is not in the cache.
        Returns:
            Union[None, dict]: The cache entry if the commit is in the cache, None otherwise.
                The dict contains the sha entry and an explanation entry.
        """
        cache = lookup_in_cache(
            commit, self.repo_slug, self.sha_cache_directory, set_run=start_merge
        )
        if cache is None:
            return None
        if not isinstance(cache, dict):
            raise TypeError("Cache entry should be a dictionary")
        return cache

    def get_test_cache_entry(
        self, sha: str, start_test: bool = False
    ) -> Tuple[Union[None, TEST_STATE], float]:
        """Gets a test cache entry.
        Args:
            sha (str): The tree fingerprint of the repository.
            start_test (bool, optional) = False: Whether to indicate that the test starts if the
                entry is not in the cache.
        Returns:
            Union[None,TEST_STATE]: The result of the test if the repository is in the cache,
                    None otherwise.
            float: The test coverage.
        """
        cache = lookup_in_cache(
            sha, self.repo_slug, self.test_cache_directory, set_run=start_test
        )
        if cache is None:
            return None, 0
        if not isinstance(cache, dict):
            raise TypeError("Cache entry should be a dictionary")
        return TEST_STATE[cache["test_result"]], cache["test_coverage"][-1]

    def _checkout_and_test(
        self,
        commit: str,
        timeout: int,
        n_tests: int,
    ) -> Tuple[TEST_STATE, float, Union[str, None]]:
        """Helper function for `checkout_and_test`,
        which checks out the given commit and tests the repository.
        This function does not check the cache.
        Args:
            commit (str): The commit to checkout.
            timeout (int): The timeout limit, in seconds.
            n_tests (int): The number of times to run the test suite.
        Returns:
            TEST_STATE: The result of the test.
            float: The test coverage.
            Union[str,None]: The tree fingerprint of the result.
        """
        result, _ = self.checkout(commit)
        if not result:
            return TEST_STATE.Git_checkout_failed, 0, None
        assert self.local_repo_path.exists(), f"Repo {self.repo_slug} does not exist"
        sha = self.compute_tree_fingerprint()
        result, test_coverage = self.test(timeout, n_tests)
        return result, test_coverage, sha

    def checkout_and_test(
        self,
        commit: str,
        timeout: int,
        n_tests: int,
    ) -> Tuple[TEST_STATE, float, Union[str, None]]:
        """Checks out the given commit and tests the repository.
        Args:
            commit (str): The commit to checkout.
            timeout (int): The timeout limit, in seconds.
            n_tests (int): The number of times to run the test suite.
            check_cache (bool, optional) = True: Whether to check the cache.
        Returns:
            TEST_STATE: The result of the test.
            float: The test coverage.
            Union[str,None]: The tree fingerprint of the result.
        """
        sha_cache_entry = self.get_sha_cache_entry(commit, start_merge=True)
        if sha_cache_entry is None:
            return self._checkout_and_test(commit, timeout, n_tests)
        if sha_cache_entry["sha"] is None:
            return TEST_STATE.Git_checkout_failed, 0, None
        result, test_coverage = self.get_test_cache_entry(sha_cache_entry["sha"])
        if result is None:
            return self._checkout_and_test(commit, timeout, n_tests)
        return result, test_coverage, sha_cache_entry["sha"]

    def test(
        self,
        timeout: int,
        n_tests: int,
        use_cache: bool = True,
        test_log_file: Union[None, Path] = None,
    ) -> Tuple[TEST_STATE, float]:
        """Tests the repository. The test results of multiple runs is combined into one result.
        If one of the runs passes then the entire test is marked as passed.
        If one of the runs timeouts then the entire test is marked as timeout.
        Otherwise all runs must fail for the entire test to be marked as failed.
        Args:
            timeout (int): The timeout limit, in seconds.
            n_tests (int): The number of times to run the test suite.
            use_cache (bool, optional) = True: Whether to check the cache.
            test_log_file (Union[None,Path], optional) = None: The path to the test log file.
        Returns:
            TEST_STATE: The result of the test.
            float: The test coverage.
        """
        sha = self.compute_tree_fingerprint()
        cache_data = {}

        if use_cache:
            result, test_coverage = self.get_test_cache_entry(sha, start_test=True)
            if result is not None:
                return result, test_coverage

        cache_data["test_results"] = []
        cache_data["test_log_file"] = []
        cache_data["test_coverage"] = []
        for i in range(n_tests):
            logger.debug(
                f"test: Running test {i+1}/{n_tests} for {self.repo_slug} at {sha}"
            )
            test_state, test_output = repo_test(self.local_repo_path, timeout)
            if test_log_file is None:
                test_log_file = Path(
                    os.path.join(
                        self.test_cache_directory,
                        "logs",
                        self.repo_slug,
                        sha + "_" + str(i) + ".log",
                    )
                )
            test_log_file.parent.mkdir(parents=True, exist_ok=True)
            if test_log_file.exists():
                test_log_file.unlink()
            with open(test_log_file, "w", encoding="utf-8") as f:
                f.write(test_output)
            cache_data["test_results"].append(test_state.name)
            cache_data["test_log_file"].append(str(test_log_file))
            cache_data["test_result"] = test_state.name
            cache_data["test_coverage"].append(self.compute_test_coverage())
            if test_state in (TEST_STATE.Tests_passed, TEST_STATE.Tests_timedout):
                break
        if use_cache:
            set_in_cache(sha, cache_data, self.repo_slug, self.test_cache_directory)
        return TEST_STATE[cache_data["test_result"]], cache_data["test_coverage"][-1]

    def compute_test_coverage(self) -> float:
        """Computes the test coverage of the given commit.
        Args:
            commit (str): The commit to checkout.
        Returns:
            float: The test coverage.
        """
        jacoco_file = self.local_repo_path / Path("target/site/jacoco/jacoco.xml")
        if not jacoco_file.exists():
            return 0
        try:
            tree = ET.parse(jacoco_file)
        except ET.ParseError:
            return 0
        root = tree.getroot()

        total_missed = 0
        total_covered = 0

        for counter in root.findall(".//counter[@type='INSTRUCTION']"):
            total_missed += int(counter.attrib["missed"])
            total_covered += int(counter.attrib["covered"])

        total = total_missed + total_covered
        if total == 0:
            return 0
        return total_covered / total

    def get_head_hash(self) -> str:
        """Gets the hash of the head commit.
        Returns:
            str: The hash of the head commit.
        """
        return self.repo.head.commit.hexsha

    def run_command(self, command: str) -> Tuple[str, str]:
        """Runs a command in the repository.
        Args:
            command (str): The command to run.
        Returns:
            Tuple[str,str]: The standard output and standard error of the command.
        """
        if not self.local_repo_path.exists():
            self.copy_repo()
        process = subprocess.run(
            command,
            shell=True,
            cwd=self.local_repo_path,  # Ensure the command runs in the repository directory
            capture_output=True,
            text=True,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"Command {command} failed with exit code {process.returncode}:\n"
                f"In folder {self.local_repo_path}\n"
                f"stdout: {process.stdout}\nstderr: {process.stderr}"
            )
        return process.stdout, process.stderr

    def __del__(self) -> None:
        """Deletes the repository."""
        if self.delete_workdir:
            shutil.rmtree(self.workdir, ignore_errors=True)
