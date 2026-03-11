import pandas as pd

db = pd.read_csv("data/gdelt_na_events_2024_full.csv", low_memory=False)

print(db.columns)