
import pandas as pd
import torch
import torch.nn as nn
import numpy as np

from pathlib import Path
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score
)


class ValidationDataset(Dataset):
    def __init__(self, csv_file, transform):
        self.df = pd.read_csv(csv_file)
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        image = Image.open(row["image_path"]).convert("RGB")
        image = self.transform(image)
        return image, int(row["class_id"])


def main():
    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    checkpoint_path = "models/deepfake_mobilenetv3.pth"

    if not Path(checkpoint_path).exists():
        raise FileNotFoundError(checkpoint_path)

    checkpoint = torch.load(
        checkpoint_path,
        map_location=device,
        weights_only=False
    )

    model = models.mobilenet_v3_small(weights=None)
    model.classifier[3] = nn.Linear(
        model.classifier[3].in_features, 2
    )

    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()

    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            checkpoint["mean"],
            checkpoint["std"]
        )
    ])

    dataset = ValidationDataset(
        "dataset/splits/test.csv",
        transform
    )

    loader = DataLoader(
        dataset,
        batch_size=16,
        shuffle=False,
        num_workers=0
    )

    all_labels = []
    all_predictions = []
    all_fake_scores = []

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            outputs = model(images)
            probabilities = torch.softmax(outputs, dim=1)

            predictions = outputs.argmax(dim=1)

            all_labels.extend(labels.tolist())
            all_predictions.extend(predictions.cpu().tolist())
            all_fake_scores.extend(
                probabilities[:, 1].cpu().tolist()
            )

    accuracy = accuracy_score(
        all_labels, all_predictions
    )

    auc = roc_auc_score(
        all_labels, all_fake_scores
    )

    matrix = confusion_matrix(
        all_labels, all_predictions, labels=[0, 1]
    )

    print("\n===== DEEPFAKE AI VALIDATION RESULTS =====")
    print(f"Images evaluated: {len(all_labels)}")
    print(f"Checkpoint accuracy: {checkpoint['best_val_accuracy'] * 100:.2f}%")
    print(f"Full validation accuracy: {accuracy * 100:.2f}%")
    print(f"ROC-AUC: {auc:.4f}")

    print("\nConfusion Matrix:")
    print(matrix)
    print("\nRows = Actual [Real, Fake]")
    print("Columns = Predicted [Real, Fake]")

    print("\nClassification Report:")
    print(classification_report(
        all_labels,
        all_predictions,
        labels=[0, 1],
        target_names=["real", "fake"],
        zero_division=0
    ))

    print("\nPrediction distribution:")
    print("Predicted real:", all_predictions.count(0))
    print("Predicted fake:", all_predictions.count(1))


if __name__ == "__main__":
    main()
