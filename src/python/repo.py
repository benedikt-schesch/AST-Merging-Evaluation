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
import json
import fasteners
from git.repo import Repo


REPOS_PATH = Path("repos")
WORKDIR_PREFIX = Path(".workdir")
N_RESTARTS = 5
TEST_STATE = Enum(
    "TEST_STATE",
    [
        "Tests_passed",
        "Tests_failed",
        "Tests_running",
        "Tests_timedout",
    ],
)


def read_cache(cache_entry: Path) -> dict:
    """Reads the cache entry."""
    with open(cache_entry, "r") as f:
        return json.load(f)


def write_cache(cache_entry: Path, entry: dict):
    """Writes the entry to the cache."""
    with open(cache_entry, "w") as f:
        json.dump(entry, f, indent=2)


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
        self.cache_data = {}

    def checkout(self, commit: str) -> bool:
        """Checks out the given commit.
        Args:
            commit (str): The commit to checkout.
        Returns:
            bool: True if the checkout succeeded, False otherwise.
        """
        try:
            self.repo.git.checkout(commit)
            self.repo.submodule_update()
        except Exception as e:
            print("Failed to checkout", commit, "for", self.repo_name, ":", e)
            return False
        return True

    def compute_tree_fingerprint(self) -> str:
        """Computes the tree fingerprint of the repository.
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

    def test(self, timeout: int) -> TEST_STATE:
        """Tests the repository.
        Args:
            timeout (int): The timeout limit.
        Returns:
            TEST_STATE: The result of the test.
        """
        sha = self.compute_tree_fingerprint()
        cache_entry_name = sha + ".json"
        cache_entry = self.cache_prefix / self.repo_name / cache_entry_name
        cache_entry.parent.mkdir(parents=True, exist_ok=True)

        lock = fasteners.InterProcessLock(str(cache_entry) + ".lock")
        with lock:
            if cache_entry.exists():
                self.cache_data = read_cache(cache_entry)
                return TEST_STATE[self.cache_data["test_result"]]
            self.cache_data["test_result"] = TEST_STATE.Tests_running.name
            write_cache(cache_entry, self.cache_data)

        self.cache_data["tests"] = []
        self.cache_data["test_log_file"] = []
        for i in range(N_RESTARTS):
            test, explanation = repo_test(self.repo_path, timeout)
            test_log_file = Path(
                str(cache_entry).replace(".json", "_" + str(i) + ".log")
            )
            with open(test_log_file, "w") as f:
                f.write(explanation)
            self.cache_data["tests"].append(test.name)
            self.cache_data["test_log_file"].append(str(test_log_file))
            self.cache_data["test_result"] = test.name
            if test in (TEST_STATE.Tests_passed, TEST_STATE.Tests_timedout):
                break

        with lock:
            write_cache(cache_entry, self.cache_data)
        return TEST_STATE[self.cache_data["test_result"]]

    def __del__(self) -> None:
        """Deletes the repository."""
        shutil.rmtree(self.workdir)
