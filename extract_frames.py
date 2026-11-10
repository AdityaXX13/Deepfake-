
import cv2
from pathlib import Path
from tqdm import tqdm

# Correct FaceForensics++ location
BASE_DIR = Path("dataset/dataset/ffpp")

OUTPUT_DIR = Path("dataset/frames")

VIDEO_TYPES = {
    "real": BASE_DIR / "original_sequences" / "youtube" / "c23" / "videos",
    "fake": BASE_DIR / "manipulated_sequences" / "Deepfakes" / "c23" / "videos"
}

FRAMES_PER_VIDEO = 10

def extract_frames(video_path, output_dir):
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        print(f"Cannot open: {video_path.name}")
        return 0

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if total <= 0:
        cap.release()
        return 0

    saved = 0

    for i in range(FRAMES_PER_VIDEO):
        frame_no = int(i * total / FRAMES_PER_VIDEO)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)

        success, frame = cap.read()

        if not success:
            continue

        frame = cv2.resize(frame, (224, 224))

        filename = output_dir / f"frame_{i:03d}.jpg"

        if cv2.imwrite(str(filename), frame):
            saved += 1

    cap.release()
    return saved


def main():
    for label, video_folder in VIDEO_TYPES.items():

        if not video_folder.exists():
            print(f"\nFolder not found: {video_folder}")
            continue

        videos = list(video_folder.glob("*.mp4"))

        print(f"\n{label.upper()}: {len(videos)} videos found")

        total_saved = 0

        for video in tqdm(videos, desc=label):
            output_folder = OUTPUT_DIR / label / video.stem
            output_folder.mkdir(parents=True, exist_ok=True)

            total_saved += extract_frames(video, output_folder)

        print(f"{label}: {total_saved} frames saved")

    print("\nExtraction process completed!")


if __name__ == "__main__":
    main()
