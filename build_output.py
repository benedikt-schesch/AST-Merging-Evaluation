# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd

df = pd.read_csv(Path("results/combined_sampled_50/result_raw.csv"))

idx = 3

print("Deepseek:", df.iloc[idx]["deepseekr1_merge"])
print("Mergiraf:", df.iloc[idx]["mergiraf"])

left = df.iloc[idx]["left"]
right = df.iloc[idx]["right"]
prefix = df.iloc[idx]["repository"]
owner_name = prefix.split("/")[0]

path = Path(
    f"cache/sha_cache_entry/{owner_name}/logs/{left}_{right}_deepseekr1_merge.log"
)

# Print absolute path
print(path.resolve())
