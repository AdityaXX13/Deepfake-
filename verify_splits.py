import pandas as pd
from pathlib import Path

files = [
    "dataset/splits/train.csv",
    "dataset/splits/val.csv",
    "dataset/splits/test.csv"
]

for file in files:
    print("\n" + "=" * 45)
    print("FILE:", file)

    df = pd.read_csv(file)

    print("\nClass distribution:")
    print(df["label"].value_counts())

    print("\nTotal images:", len(df))
    print("Unique videos:", df["video_id"].nunique())

    print("\nMissing image files:")
    missing = sum(not Path(p).exists() for p in df["image_path"])
    print(missing)

    print("\nClass ID check:")
    print(df.groupby(["label", "class_id"]).size())

