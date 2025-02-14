# -*- coding: utf-8 -*-
"""Contains all used variables."""

from pathlib import Path
import os

BRANCH_BASE_NAME = "___MERGE_TESTER"
LEFT_BRANCH_NAME = BRANCH_BASE_NAME + "_LEFT"
RIGHT_BRANCH_NAME = BRANCH_BASE_NAME + "_RIGHT"

CACHE_BACKOFF_TIME = 2 * 60  # 2 minutes, in seconds
DELETE_WORKDIRS = os.getenv("DELETE_WORKDIRS", "True").lower() in ["true", "1", "yes"]
REPOS_PATH = (
    Path(os.getenv("AST_REPOS_PATH")) if os.getenv("AST_REPOS_PATH") else Path("repos")
)
WORKDIR_DIRECTORY = Path(
    os.getenv("WORKDIR_DIRECTORY", ".workdir")
)  # Merges and testing will be performed in this directory.

TIMEOUT_MERGING = 60 * 60  # 60 minutes, in seconds

TIMEOUT_TESTING_PARENT = 60 * 30  # 30 minutes, in seconds
TIMEOUT_TESTING_MERGE = 60 * 45  # 45 minutes, in seconds
N_TESTS = 5
