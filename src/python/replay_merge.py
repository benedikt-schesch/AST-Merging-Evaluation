# -*- coding: utf-8 -*-
"""Replay merges and their test results"""
import argparse
import shutil
from pathlib import Path
from tqdm import tqdm
import pandas as pd
from repo import Repository, MERGE_TOOL, TEST_STATE, MERGE_STATE
from variables import TIMEOUT_TESTING_MERGE, N_TESTS


def merge_replay(
    repo_slug: str, merge_data: pd.Series, test_merge: bool
) -> pd.DataFrame:
    """Replay a merge and its test results.
    Args:
        args (Tuple[str,pd.Series]): A tuple containing the repository slug,
                    the repository info, and the cache path.
    Returns:
        pd.Series: The result of the test.
    """
    print("merge_replay: Started ", repo_slug, merge_data["left"], merge_data["right"])
    result_df = pd.DataFrame()
    for merge_tool in tqdm(MERGE_TOOL):
        repo = Repository(
            repo_slug,
            cache_directory=Path("no_cache/"),
            workdir_id=repo_slug
            + f"/merge-tester-{merge_tool.name}-"
            + f'{merge_data["left"]}-{merge_data["right"]}',
            delete_workdir=False,
        )
        (
            merge_result,
            merge_fingerprint,
            left_fingerprint,
            right_fingerprint,
            explanation,
            _,
        ) = repo.merge(
            tool=merge_tool,
            left_commit=merge_data["left"],
            right_commit=merge_data["right"],
            timeout=TIMEOUT_TESTING_MERGE,
            use_cache=False,
        )
        assert merge_data[f"{merge_tool.name}_merge_fingerprint"] == merge_fingerprint
        root_dir = Path("replay_logs")
        log_path = root_dir / Path(
            "merges/"
            + repo_slug
            + "-"
            + merge_data["left"]
            + "-"
            + merge_data["right"]
            + "-"
            + merge_tool.name
            + ".log"
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(explanation)
        result_df.loc[
            merge_tool.name,
            ["merge result", "merge log path", "repo path"],
        ] = [
            merge_result.name,
            log_path,
            repo.repo_path,
        ]

        if merge_result not in (
            MERGE_STATE.Merge_failed,
            MERGE_STATE.Git_checkout_failed,
            TEST_STATE.Git_checkout_failed,
        ) and (
            left_fingerprint != merge_data["left_tree_fingerprint"]
            or right_fingerprint != merge_data["right_tree_fingerprint"]
        ):
            raise Exception(
                "merge_replay: The merge tester is not testing the correct merge.",
                merge_result,
                repo_slug,
                merge_data["left"],
                merge_data["right"],
                left_fingerprint,
                right_fingerprint,
                merge_data["left_tree_fingerprint"],
                merge_data["right_tree_fingerprint"],
                merge_data,
            )
        if merge_result == MERGE_STATE.Merge_success:
            log_path = root_dir / Path(
                "merge_tests/"
                + repo_slug
                + "-"
                + merge_data["left"]
                + "-"
                + merge_data["right"]
                + "-"
                + merge_tool.name
                + ".log"
            )
            if test_merge:
                test_result, _ = repo.test(
                    timeout=TIMEOUT_TESTING_MERGE,
                    n_tests=N_TESTS,
                    use_cache=False,
                    test_log_file=log_path,
                )
                result_df.loc[
                    merge_tool.name,
                    ["merge test result", "merge test log path"],
                ] = [
                    test_result.name,
                    log_path,
                ]
                assert merge_data[f"{merge_tool.name}"] == test_result.name
    return result_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--merges_csv",
        help="CSV file with merges that have been tested",
        type=str,
        default="results/result.csv",
    )
    parser.add_argument(
        "--idx",
        help="Index of the merge to replay",
        type=int,
        default=0,
    )
    parser.add_argument(
        "-test",
        help="Test the replay of a merge",
        action="store_true",
    )
    arguments = parser.parse_args()

    df = pd.read_csv(arguments.merges_csv, index_col="idx")

    repo_slug = df.loc[arguments.idx, "repository"]
    merge_data = df.loc[arguments.idx]
    repo = Repository(  # To clone the repo
        str(repo_slug),
        cache_directory=Path("no_cache/"),
        workdir_id="todelete",
    )
    shutil.rmtree(repo.path, ignore_errors=True)
    results_df = merge_replay(str(repo_slug), merge_data, arguments.test)
    for idx, row in results_df.iterrows():
        print("=====================================")
        print("Merge tool:", idx)
        print("Merge result:", row["merge result"])
        print("Merge log path:", row["merge log path"])
        if row["merge result"] == MERGE_STATE.Merge_success and arguments.test:
            print("Merge test result:", row["merge test result"])
            print("Merge test log path:", row["merge test log path"])
        print("merge data test result:", merge_data[idx])
        print("repo location:", row["repo path"])
