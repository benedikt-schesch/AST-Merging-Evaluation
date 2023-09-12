"""Contains all used variables."""

from pathlib import Path

BRANCH_BASE_NAME = "___MERGE_TESTER"
LEFT_BRANCH_NAME = BRANCH_BASE_NAME + "_LEFT"
RIGHT_BRANCH_NAME = BRANCH_BASE_NAME + "_RIGHT"

CACHE_BACKOFF_TIME = 2 * 60  # 2 minutes, in seconds
DELETE_WORKDIRS = True
REPOS_PATH = Path("repos")
WORKDIR_PREFIX = Path(".workdir")

TIMEOUT_MERGING = 60 * 15  # 15 minutes, in seconds
N_REPETITIONS = 3
