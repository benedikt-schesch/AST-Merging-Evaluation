# -*- coding: utf-8 -*-
"""Script to compute and verify SHA256 hashes for all files in a directory."""

import json
import subprocess
from pathlib import Path
import shutil
from rich.progress import Progress, TaskID
import argparse


def compute_tree_filehash_map(repo_path: Path) -> str:
    """
    Computes a SHA256 for every file in the repository (excluding .git) and
    returns a JSON string mapping each file path to its hash.

    Args:
        repo_path (Path): Path object pointing to the local repository folder.

    Returns:
        str: JSON string that maps from file path to its SHA256 hash.
    """
    assert repo_path.exists(), f"Repository path {repo_path} does not exist"

    command = (
        "export LC_ALL=C; export LC_COLLATE=C; cd "
        + str(repo_path)
        + " ; find . -type f -not -path '*/\\.git*' -exec sha256sum {} \\; | sort"
    )

    output = subprocess.check_output(command, shell=True, executable="/bin/bash")
    lines = output.decode("utf-8").strip().split("\n")

    filehash_map = {}
    for line in lines:
        if not line.strip():
            continue
        sha, path = line.split("  ", 1)
        cleaned_path = path.lstrip("./")
        filehash_map[cleaned_path] = sha

    return json.dumps(filehash_map, indent=2)


def process_directory(
    progress: Progress, task_id: TaskID, dir3: Path, hash_dir: Path, mode: str
):
    """
    Processes a single directory by computing or verifying hashes.

    Args:
        progress (Progress): Rich progress bar instance.
        task_id (TaskID): Task ID for progress tracking.
        dir3 (Path): Directory being processed.
        hash_dir (Path): Path to the hash file.
        mode (str): Either "create" or "verify".
    """
    if mode == "create":
        hash_dir.parent.mkdir(parents=True, exist_ok=True)
        hash_map = compute_tree_filehash_map(dir3)
        with open(hash_dir, "w", encoding="utf-8") as hash_file:
            hash_file.write(hash_map)
    elif mode == "verify":
        if not hash_dir.exists():
            print(f"Hash file for {dir3} not found")
            exit(1)
        with open(hash_dir, "r", encoding="utf-8") as hash_file:
            stored_hash_map = json.load(hash_file)
        current_hash_map = json.loads(compute_tree_filehash_map(dir3))

        for file, stored_hash in stored_hash_map.items():
            if file not in current_hash_map:
                print(f"File {file} missing in current hashes for {dir3}")
                exit(1)
            if current_hash_map[file] != stored_hash:
                print(f"Hash mismatch for file {file} in {dir3}")
                print(f"File path: {dir3 / file}")
                print(f"Stored hash: {stored_hash}")
                print(f"Current hash: {current_hash_map[file]}")
                print("File content:")
                with open(dir3 / file, "r", encoding="utf-8") as file_content:
                    print(file_content.read())
                exit(1)
    progress.update(task_id, advance=1)


def main():
    """Main function to process and verify directory hashes."""
    parser = argparse.ArgumentParser(description="Process and verify directory hashes.")
    parser.add_argument(
        "--override",
        action="store_true",
        help="Override existing hashes with newly computed ones.",
    )
    parser.add_argument(
        "--goal_path",
        type=Path,
        help="Path to the directory where hash files will be stored.",
        default=Path("test/small-goal-files/hashes"),
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        help="Path to the directory containing the directories to be processed.",
        default=Path(".workdir-small-test"),
    )
    args = parser.parse_args()

    base_path = args.goal_path
    workdir_path = args.workdir

    # Collect all level-3 directories
    dir3_list = []
    for dir1 in workdir_path.iterdir():
        if dir1.is_dir():
            for dir2 in dir1.iterdir():
                if dir2.is_dir():
                    for dir3 in dir2.iterdir():
                        if dir3.is_dir():
                            dir3_list.append((dir1.name, dir2.name, dir3.name, dir3))

    with Progress() as progress:
        task_id = progress.add_task("Processing directories...", total=len(dir3_list))

        if not base_path.exists() or args.override:
            # Case 1: Create directories and generate hash mappings
            shutil.rmtree(base_path, ignore_errors=True)
            if not base_path.exists():
                base_path.mkdir(parents=True, exist_ok=True)
            for dir1_name, dir2_name, dir3_name, dir3 in dir3_list:
                hash_dir = base_path / dir1_name / dir2_name / dir3_name
                process_directory(
                    progress,
                    task_id,
                    dir3,
                    hash_dir.with_suffix(".json"),
                    mode="create",
                )
        else:
            # Case 2: Verify hashes
            for dir1_name, dir2_name, dir3_name, dir3 in dir3_list:
                hash_dir = base_path / dir1_name / dir2_name / dir3_name
                process_directory(
                    progress,
                    task_id,
                    dir3,
                    hash_dir.with_suffix(".json"),
                    mode="verify",
                )

    print("All hashes processed successfully")


if __name__ == "__main__":
    main()
