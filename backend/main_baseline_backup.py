from fastapi import FastAPI, File, UploadFile, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from pathlib import Path
from datetime import datetime, timezone
from PIL import Image
import sqlite3
import secrets
import hashlib
import os
import io
import tempfile
import threading

import torch
import torch.nn as nn
from torchvision import models, transforms


# ------------------------------------------------------------
# PATHS AND SETTINGS
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
# Render deployment: set DB_PATH=/app/data/deepfake.db
# Local development: defaults to the project-root deepfake.db
DB = Path(os.getenv("DB_PATH", str(BASE_DIR / "deepfake.db")))
DB.parent.mkdir(parents=True, exist_ok=True)

MODEL_PATH = BASE_DIR / "models" / "deepfake_mobilenetv3.pth"

MAX_BYTES = 200 * 1024 * 1024
MAX_VIDEO_FRAMES = 12

DEVICE = torch.device("cpu")
MODEL = None
CHECKPOINT = None
MODEL_LOAD_ERROR = None
MODEL_LOCK = threading.Lock()

app = FastAPI(title="DeepFAke AI", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT NOT NULL,
        media_type TEXT NOT NULL,
        verdict TEXT NOT NULL,
        confidence REAL NOT NULL,
        frames INTEGER NOT NULL,
        faces INTEGER NOT NULL,
        created_at TEXT NOT NULL
    );
    """)
    con.commit()
    con.close()


init_db()


# ------------------------------------------------------------
# LOAD TRAINED MOBILENETV3 MODEL
# ------------------------------------------------------------

def load_model():
    global MODEL, CHECKPOINT, MODEL_LOAD_ERROR

    try:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model checkpoint not found: {MODEL_PATH}"
            )

        checkpoint = torch.load(
            MODEL_PATH,
            map_location=DEVICE,
            weights_only=False
        )

        if checkpoint.get("architecture") != "mobilenet_v3_small":
            raise ValueError("Unsupported model architecture.")

        class_map = checkpoint.get("class_map", {})

        if "real" not in class_map or "fake" not in class_map:
            raise ValueError("Checkpoint has an invalid class map.")

        model = models.mobilenet_v3_small(weights=None)

        # The trained checkpoint has a two-class output layer.
        in_features = model.classifier[3].in_features
        model.classifier[3] = nn.Linear(in_features, 2)

        model.load_state_dict(
            checkpoint["model_state_dict"],
            strict=True
        )

        model.to(DEVICE)
        model.eval()

        MODEL = model
        CHECKPOINT = checkpoint
        MODEL_LOAD_ERROR = None

        print("DeepFAke AI: trained MobileNetV3 model loaded.")
        print("Class map:", class_map)
        print("Saved validation accuracy:",
              checkpoint.get("best_val_accuracy"))

    except Exception as error:
        MODEL = None
        CHECKPOINT = None
        MODEL_LOAD_ERROR = str(error)
        print("MODEL LOAD ERROR:", MODEL_LOAD_ERROR)


load_model()


# ------------------------------------------------------------
# IMAGE PREPROCESSING
# ------------------------------------------------------------

def get_transform():
    if CHECKPOINT is None:
        raise RuntimeError("Trained model is not loaded.")

    image_size = int(CHECKPOINT.get("image_size", 224))
    mean = CHECKPOINT.get("mean", [0.485, 0.456, 0.406])
    std = CHECKPOINT.get("std", [0.229, 0.224, 0.225])

    return transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=mean, std=std)
    ])


def predict_image(image):
    if MODEL is None:
        raise RuntimeError(
            f"Trained model unavailable: {MODEL_LOAD_ERROR}"
        )

    image = image.convert("RGB")
    tensor = get_transform()(image).unsqueeze(0).to(DEVICE)

    with MODEL_LOCK:
        with torch.inference_mode():
            output = MODEL(tensor)
            probabilities = torch.softmax(output, dim=1)[0]

    class_map = CHECKPOINT["class_map"]
    real_index = int(class_map["real"])
    fake_index = int(class_map["fake"])

    real_probability = float(probabilities[real_index].item())
    fake_probability = float(probabilities[fake_index].item())

    is_fake = fake_probability >= real_probability

    return {
        "verdict": "Likely fake" if is_fake else "Likely authentic",
        "confidence": max(real_probability, fake_probability),
        "real_probability": real_probability,
        "fake_probability": fake_probability,
        "predicted_class": "fake" if is_fake else "real"
    }


# ------------------------------------------------------------
# FACE COUNT (SUPPLEMENTARY ONLY)
# ------------------------------------------------------------

def count_faces(image):
    try:
        import cv2
        import numpy as np

        rgb = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

        cascade_path = (
            cv2.data.haarcascades
            + "haarcascade_frontalface_default.xml"
        )

        detector = cv2.CascadeClassifier(cascade_path)

        if detector.empty():
            return 0

        return len(
            detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5
            )
        )

    except Exception:
        return 0


# ------------------------------------------------------------
# AUTHENTICATION
# ------------------------------------------------------------

class AuthIn(BaseModel):
    email: EmailStr
    password: str


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        bytes.fromhex(salt),
        120_000
    ).hex()

    return digest, salt


def token_from_header(authorization):
    if not authorization:
        return None

    if not authorization.lower().startswith("bearer "):
        return None

    return authorization.split(" ", 1)[1].strip()


def get_user(token):
    if not token:
        return None

    con = db()

    row = con.execute("""
        SELECT u.*
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ?
    """, (token,)).fetchone()

    con.close()
    return row


@app.post("/api/register")
def register(payload: AuthIn):
    if len(payload.password) < 6:
        raise HTTPException(
            400,
            "Password must contain at least 6 characters."
        )

    email = payload.email.lower().strip()
    digest, salt = hash_password(payload.password)

    con = db()

    try:
        cur = con.execute("""
            INSERT INTO users(email, password_hash, salt, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            email,
            digest,
            salt,
            datetime.now(timezone.utc).isoformat()
        ))

        uid = cur.lastrowid
        token = secrets.token_urlsafe(32)

        con.execute("""
            INSERT INTO sessions(token, user_id, created_at)
            VALUES (?, ?, ?)
        """, (
            token,
            uid,
            datetime.now(timezone.utc).isoformat()
        ))

        con.commit()

        return {
            "token": token,
            "user": {"id": uid, "email": email}
        }

    except sqlite3.IntegrityError:
        raise HTTPException(
            409,
            "An account with this email already exists."
        )

    finally:
        con.close()


@app.post("/api/login")
def login(payload: AuthIn):
    email = payload.email.lower().strip()

    con = db()
    row = con.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if not row:
        con.close()
        raise HTTPException(401, "Invalid email or password.")

    digest, _ = hash_password(payload.password, row["salt"])

    if not secrets.compare_digest(
        digest,
        row["password_hash"]
    ):
        con.close()
        raise HTTPException(401, "Invalid email or password.")

    token = secrets.token_urlsafe(32)

    con.execute("""
        INSERT INTO sessions(token, user_id, created_at)
        VALUES (?, ?, ?)
    """, (
        token,
        row["id"],
        datetime.now(timezone.utc).isoformat()
    ))

    con.commit()
    con.close()

    return {
        "token": token,
        "user": {"id": row["id"], "email": row["email"]}
    }


@app.get("/api/me")
def me(authorization: str = Header(default="")):
    user = get_user(token_from_header(authorization))

    if not user:
        raise HTTPException(401, "Not authenticated.")

    return {
        "id": user["id"],
        "email": user["email"]
    }


@app.post("/api/logout")
def logout(authorization: str = Header(default="")):
    token = token_from_header(authorization)

    if token:
        con = db()
        con.execute(
            "DELETE FROM sessions WHERE token = ?",
            (token,)
        )
        con.commit()
        con.close()

    return {"ok": True}


# ------------------------------------------------------------
# SAVE SCAN HISTORY
# ------------------------------------------------------------

def save_scan(user_id, filename, media_type, result):
    con = db()

    con.execute("""
        INSERT INTO scans(
            user_id, filename, media_type,
            verdict, confidence, frames, faces, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        filename,
        media_type,
        result["verdict"],
        result["confidence"],
        result["frames"],
        result["faces"],
        datetime.now(timezone.utc).isoformat()
    ))

    con.commit()
    con.close()


# ------------------------------------------------------------
# HEALTH CHECK
# ------------------------------------------------------------

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "DeepFAke AI",
        "model_ready": MODEL is not None,
        "mode": "trained_mobilenetv3" if MODEL else "model_unavailable",
        "device": str(DEVICE),
        "model_error": MODEL_LOAD_ERROR
    }


# ------------------------------------------------------------
# IMAGE DETECTION
# ------------------------------------------------------------

@app.post("/api/detect-image")
async def detect_image(
    file: UploadFile = File(...),
    authorization: str = Header(default="")
):
    data = await file.read(MAX_BYTES + 1)

    if not data:
        raise HTTPException(400, "Empty image file.")

    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large.")

    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        raise HTTPException(400, "Invalid image file.")

    try:
        prediction = predict_image(image)
    except Exception as error:
        raise HTTPException(503, str(error))

    faces = count_faces(image)

    result = {
        **prediction,
        "frames": 1,
        "faces": faces
    }

    user = get_user(token_from_header(authorization))

    save_scan(
        user["id"] if user else None,
        file.filename or "image",
        "image",
        result
    )

    return {
        "status": "Complete",
        **result,
        "media_type": "image",
        "engine": "MobileNetV3-Small",
        "confidence_level": "MODEL SCORE - NOT CALIBRATED",
        "note": (
            "Prediction generated by the trained MobileNetV3 model. "
            "The score is not a calibrated probability or a guarantee "
            "of authenticity."
        )
    }


# ------------------------------------------------------------
# VIDEO DETECTION
# ------------------------------------------------------------

@app.post("/api/detect-video")
async def detect_video(
    file: UploadFile = File(...),
    authorization: str = Header(default="")
):
    data = await file.read(MAX_BYTES + 1)

    if not data:
        raise HTTPException(400, "Empty video file.")

    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large.")

    suffix = Path(file.filename or "video.mp4").suffix.lower()

    allowed_extensions = {
        ".mp4", ".avi", ".mov", ".mkv", ".webm", ".mpeg", ".mpg"
    }

    if suffix not in allowed_extensions:
        raise HTTPException(400, "Unsupported video format.")

    try:
        import cv2

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as tmp:
            tmp.write(data)
            temp_path = tmp.name

        cap = cv2.VideoCapture(temp_path)

        if not cap.isOpened():
            raise HTTPException(
                400,
                "Unable to open video. Check its format or codec."
            )

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        duration = total_frames / fps if fps > 0 else 0

        if total_frames <= 0:
            cap.release()
            raise HTTPException(400, "Video contains no readable frames.")

        sample_count = min(MAX_VIDEO_FRAMES, total_frames)

        if sample_count == 1:
            frame_indices = [0]
        else:
            frame_indices = [
                round(i * (total_frames - 1) / (sample_count - 1))
                for i in range(sample_count)
            ]

        fake_scores = []
        real_scores = []
        faces_total = 0
        frames_analyzed = 0

        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades
            + "haarcascade_frontalface_default.xml"
        )

        for frame_index in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()

            if not ok:
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)

            prediction = predict_image(image)

            fake_scores.append(prediction["fake_probability"])
            real_scores.append(prediction["real_probability"])

            if not cascade.empty():
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces_total += len(
                    cascade.detectMultiScale(
                        gray,
                        scaleFactor=1.1,
                        minNeighbors=5
                    )
                )

            frames_analyzed += 1

        cap.release()

        if frames_analyzed == 0:
            raise HTTPException(400, "No video frames could be analyzed.")

        mean_fake = sum(fake_scores) / len(fake_scores)
        mean_real = sum(real_scores) / len(real_scores)

        is_fake = mean_fake >= mean_real

        prediction = {
            "verdict": "Likely fake" if is_fake else "Likely authentic",
            "confidence": max(mean_fake, mean_real),
            "real_probability": mean_real,
            "fake_probability": mean_fake,
            "predicted_class": "fake" if is_fake else "real"
        }

        result = {
            **prediction,
            "frames": frames_analyzed,
            "faces": faces_total
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            400,
            f"Video analysis failed: {error}"
        )

    finally:
        if "temp_path" in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)

    user = get_user(token_from_header(authorization))

    save_scan(
        user["id"] if user else None,
        file.filename or "video",
        "video",
        result
    )

    return {
        "status": "Complete",
        **result,
        "media_type": "video",
        "engine": "MobileNetV3-Small",
        "confidence_level": "MODEL SCORE - NOT CALIBRATED",
        "duration_seconds": round(duration, 2),
        "note": (
            f"Analyzed {frames_analyzed} sampled frames. "
            "The video score is the average frame-level model score. "
            "It is not a calibrated probability or a guarantee."
        )
    }


# ------------------------------------------------------------
# SCAN HISTORY
# ------------------------------------------------------------

@app.get("/api/history")
def history(authorization: str = Header(default="")):
    user = get_user(token_from_header(authorization))

    if not user:
        return []

    con = db()

    rows = con.execute("""
        SELECT filename, media_type, verdict, confidence,
               frames, faces, created_at
        FROM scans
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 20
    """, (user["id"],)).fetchall()

    con.close()

    return [dict(row) for row in rows]


# ------------------------------------------------------------
# FRONTEND
# ------------------------------------------------------------

app.mount(
    "/",
    StaticFiles(
        directory=str(FRONTEND_DIR),
        html=True
    ),
    name="frontend"
)