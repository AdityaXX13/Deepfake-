import pandas as pd
from pathlib import Path

files = {
    "train": "dataset/splits/train.csv",
    "val": "dataset/splits/val.csv",
    "test": "dataset/splits/test.csv"
}

source_splits = {}

for split, file in files.items():
    df = pd.read_csv(file, dtype={"video_id": str})

    for video_id in df["video_id"].dropna().unique():
        # Fake video IDs such as 015_919 contain source IDs
        source_ids = video_id.split("_")

        for source_id in source_ids:
            source_splits.setdefault(source_id, set()).add(split)

leaks = {
    source: splits
    for source, splits in source_splits.items()
    if len(splits) > 1
}

print("Potential source-video leakage:", len(leaks))
for source, splits in list(leaks.items())[:20]:
    print(source, sorted(splits))

print("\nPyTorch check:")
try:
    import torch
    import torchvision
    print("PyTorch:", torch.__version__)
    print("Torchvision:", torchvision.__version__)
    print("CUDA:", torch.cuda.is_available())
except Exception as e:
    print("PyTorch error:", e)
