"""Tests the run small data"""

import subprocess
import pandas as pd


def test_small():
    """
    Test the run small example
    """
    subprocess.run(["./run_small.sh"], shell=True)
    result = pd.read_csv("small/result.csv")
    assert len(result) == 4
