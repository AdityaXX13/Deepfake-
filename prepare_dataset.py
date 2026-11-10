
from pathlib import Path
import random
import csv

random.seed(42)

BASE = Path("dataset/frames")
OUTPUT = Path("dataset/splits")

CLASSES = {
    "real": 0,
    "fake": 1
}

# Find videos and their frame folders
records = []

for label, class_id in CLASSES.items():
    folder = BASE / label

    if not folder.exists():
        raise FileNotFoundError(f"Missing folder: {folder}")

    for video_folder in sorted(folder.iterdir()):
        if not video_folder.is_dir():
            continue

        frames = sorted(video_folder.glob("*.jpg"))

        if frames:
            records.append({
                "video": video_folder.name,
                "label": label,
                "class_id": class_id,
                "frames": frames
            })

# Union-Find: keep related source videos together.
parent = {}

def find(x):
    parent.setdefault(x, x)
    if parent[x] != x:
        parent[x] = find(parent[x])
    return parent[x]

def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[rb] = ra

# Fake video names like 015_919 link two source videos.
for record in records:
    if record["label"] == "fake":
        parts = record["video"].split("_")
        if len(parts) == 2:
            union(parts[0], parts[1])

def group_id(record):
    name = record["video"]

    if record["label"] == "real":
        return find(name)

    parts = name.split("_")

    if len(parts) == 2:
        return find(parts[0])

    return find(name)

groups = {}

for record in records:
    gid = group_id(record)
    groups.setdefault(gid, []).append(record)

# Shuffle complete groups, never individual frames.
group_list = list(groups.values())
random.shuffle(group_list)

# Approximate 70/15/15 split by number of videos.
total = len(records)
targets = {
    "train": total * 0.70,
    "val": total * 0.15,
    "test": total * 0.15
}

splits = {"train": [], "val": [], "test": []}

for group in group_list:
    current = len(splits["train"]) + len(splits["val"]) + len(splits["test"])

    if len(splits["train"]) < targets["train"]:
        destination = "train"
    elif len(splits["val"]) < targets["val"]:
        destination = "val"
    else:
        destination = "test"

    splits[destination].extend(group)

OUTPUT.mkdir(parents=True, exist_ok=True)

for split_name, items in splits.items():
    csv_path = OUTPUT / f"{split_name}.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image_path", "label", "class_id", "video_id"])

        for item in items:
            for frame in item["frames"]:
                writer.writerow([
                    str(frame.resolve()),
                    item["label"],
                    item["class_id"],
                    item["video"]
                ])

    real_count = sum(x["label"] == "real" for x in items)
    fake_count = sum(x["label"] == "fake" for x in items)

    print(
        f"{split_name.upper()}: "
        f"{len(items)} videos | "
        f"Real: {real_count} | Fake: {fake_count}"
    )

print("\nDataset split files created:", OUTPUT.resolve())
print("Preparation completed!")
