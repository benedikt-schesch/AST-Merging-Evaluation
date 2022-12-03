import pandas as pd

df = pd.read_csv("data/result.csv")
df = df.sample(n=50,random_state=42)
df.to_csv("data/manual_review.csv")