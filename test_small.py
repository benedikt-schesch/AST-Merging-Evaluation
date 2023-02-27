import subprocess
import pandas as pd

def test_small():
    subprocess.run(["./run_small.sh"],shell=True)
    result = pd.read_csv("small/result.csv")
    assert len(result) == 4 