import argparse
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from torchvision.models import MobileNet_V3_Small_Weights
from PIL import Image
from sklearn.metrics import accuracy_score, classification_report



class DeepfakeDataset(Dataset):
    def __init__(self, csv_file, transform, max_per_class=None):
        df = pd.read_csv(csv_file)

        if max_per_class is not None:
            selected = []

            for class_id, group in df.groupby("class_id"):
                n = min(len(group), max_per_class)
                sampled = group.sample(
                    n=n,
                    random_state=42
                )
                selected.append(sampled)

            df = pd.concat(selected)
            df = df.sample(
                frac=1,
                random_state=42
            ).reset_index(drop=True)

        self.paths = df["image_path"].tolist()
        self.labels = df["class_id"].astype(int).tolist()
        self.transform = transform

        missing = [
            p for p in self.paths
            if not Path(p).is_file()
        ]

        if missing:
            raise FileNotFoundError(
                f"{len(missing)} images missing. "
                f"Example: {missing[0]}"
            )

        print(
            f"{Path(csv_file).name}: {len(self.paths)} images | "
            f"real={self.labels.count(0)} "
            f"fake={self.labels.count(1)}"
        )

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, index):
        image = Image.open(
            self.paths[index]
        ).convert("RGB")

        image = self.transform(image)

        return image, self.labels[index]



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-per-class", type=int, default=0)
    parser.add_argument("--freeze-backbone", action="store_true")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Training device:", device)

    weights = MobileNet_V3_Small_Weights.DEFAULT
    mean, std = weights.transforms().mean, weights.transforms().std

    train_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.10, contrast=0.10),
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])

    val_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])

    limit = args.max_per_class if args.max_per_class > 0 else None

    train_ds = DeepfakeDataset(
        "dataset/splits/train.csv", train_transform, limit
    )
    val_ds = DeepfakeDataset(
        "dataset/splits/val.csv", val_transform, limit
    )

    train_loader = DataLoader(
        train_ds, batch_size=args.batch_size,
        shuffle=True, num_workers=0
    )
    val_loader = DataLoader(
        val_ds, batch_size=args.batch_size,
        shuffle=False, num_workers=0
    )

    print("Loading pretrained MobileNetV3-Small...")
    model = models.mobilenet_v3_small(weights=weights)
    model.classifier[3] = nn.Linear(
        model.classifier[3].in_features, 2
    )

    if args.freeze_backbone:
        for param in model.features.parameters():
            param.requires_grad = False
        for param in model.classifier.parameters():
            param.requires_grad = False
        for param in model.classifier[3].parameters():
            param.requires_grad = True
        print("Smoke-test mode: backbone frozen.")

    model = model.to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW([
    {
        "params": list(model.features.parameters())
                  + list(model.classifier[:3].parameters()),
        "lr": 0.00001
    },
    {
        "params": model.classifier[3].parameters(),
        "lr": 0.0001
    }
], weight_decay=0.0001)
    

    best_accuracy = 0.0
    Path("models").mkdir(exist_ok=True)

    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0

        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        model.eval()
        all_labels, all_preds = [], []

        with torch.no_grad():
            for images, labels in val_loader:
                outputs = model(images.to(device))
                predictions = outputs.argmax(dim=1).cpu().tolist()
                all_preds.extend(predictions)
                all_labels.extend(labels.tolist())

        accuracy = accuracy_score(all_labels, all_preds)
        average_loss = total_loss / max(len(train_loader), 1)

        print(
            f"Epoch {epoch + 1}/{args.epochs} | "
            f"Train loss: {average_loss:.4f} | "
            f"Validation accuracy: {accuracy * 100:.2f}%"
        )

        if accuracy > best_accuracy:
            best_accuracy = accuracy
            torch.save({
                "model_state_dict": model.state_dict(),
                "class_map": {"real": 0, "fake": 1},
                "architecture": "mobilenet_v3_small",
                "image_size": 224,
                "mean": mean,
                "std": std,
                "best_val_accuracy": best_accuracy,
            }, "models/deepfake_mobilenetv3.pth")
            print("Best model checkpoint saved.")

    print("\nBest validation accuracy:", f"{best_accuracy * 100:.2f}%")
    print("\nValidation classification report:")
    print(classification_report(
        all_labels, all_preds,
        labels=[0, 1],
        target_names=["real", "fake"],
        zero_division=0
    ))
    print("Checkpoint: models/deepfake_mobilenetv3.pth")


if __name__ == "__main__":
    main()
