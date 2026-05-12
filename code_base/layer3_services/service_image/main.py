"""
Image Analyser Service — POST /analyse
Accepts one or more image URLs, runs ResNet-50 inference on each,
and returns room-type classification + condition score per image.
"""

import os
import logging
from contextlib import asynccontextmanager

import httpx
import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel, HttpUrl
from io import BytesIO

from model import PropertyImageModel
from dataset import EVAL_TRANSFORMS, IDX_TO_CLASS, CLASS_TO_IDX

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.50"))
MODEL_PATH           = os.getenv("MODEL_PATH", "./checkpoints/model.pth")
DEVICE               = torch.device("cpu")  # CPU-only deployment

# ---------------------------------------------------------------------------
# Lifespan — load model once
# ---------------------------------------------------------------------------

model_instance: PropertyImageModel | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model_instance
    logger.info("Loading PropertyImageModel from %s ...", MODEL_PATH)
    model_instance = PropertyImageModel(num_classes=6, freeze_backbone=True)

    try:
        ckpt = torch.load(MODEL_PATH, map_location=DEVICE)
        model_instance.load_state_dict(ckpt["model_state_dict"])
        logger.info("Checkpoint loaded (val_acc=%.1f%%, epoch=%d)",
                    ckpt.get("val_acc", 0) * 100, ckpt.get("epoch", 0))
    except FileNotFoundError:
        logger.warning(
            "Checkpoint not found at %s — running with random weights. "
            "Run train.py first to produce a trained model.pth.",
            MODEL_PATH,
        )

    model_instance.eval()
    logger.info("Image Analyser ready.")
    yield
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Property Image Analyser",
    description="Classifies room types and scores property condition using ResNet-50.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AnalyseRequest(BaseModel):
    image_urls: list[str]

    model_config = {
        "json_schema_extra": {
            "example": {
                "image_urls": [
                    "https://example.com/kitchen.jpg",
                    "https://example.com/living_room.jpg",
                ]
            }
        }
    }


class ImageResult(BaseModel):
    url: str
    room_type: str
    condition_score: float          # 1.0–5.0
    confidence: float               # 0.0–1.0
    all_class_scores: dict[str, float]
    low_confidence: bool
    error: str | None = None


class AnalyseResponse(BaseModel):
    results: list[ImageResult]
    processed: int
    failed: int


# ---------------------------------------------------------------------------
# Inference helpers
# ---------------------------------------------------------------------------

async def _fetch_image(url: str) -> Image.Image:
    """Download an image from a URL and return a PIL Image."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
    return Image.open(BytesIO(resp.content)).convert("RGB")


@torch.no_grad()
def _run_inference(pil_image: Image.Image) -> dict:
    """Run the model on a single PIL image and return structured predictions."""
    tensor = EVAL_TRANSFORMS(pil_image).unsqueeze(0).to(DEVICE)  # (1, 3, 224, 224)
    logits, score = model_instance(tensor)

    probs = torch.softmax(logits, dim=1).squeeze(0).tolist()
    condition_raw = score.item()  # 0–1 from sigmoid

    class_scores = {IDX_TO_CLASS[i]: round(p, 4) for i, p in enumerate(probs)}
    best_idx     = max(range(len(probs)), key=lambda i: probs[i])
    best_class   = IDX_TO_CLASS[best_idx]
    confidence   = round(probs[best_idx], 4)
    condition_score = round(condition_raw * 5, 2)   # scale to 1–5

    return {
        "room_type":       best_class,
        "condition_score": max(1.0, min(5.0, condition_score)),
        "confidence":      confidence,
        "all_class_scores": class_scores,
        "low_confidence":  confidence < CONFIDENCE_THRESHOLD,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": "resnet50-property",
        "classes": list(CLASS_TO_IDX.keys()),
        "confidence_threshold": CONFIDENCE_THRESHOLD,
    }


@app.post("/analyse", response_model=AnalyseResponse)
async def analyse(request: AnalyseRequest):
    if not request.image_urls:
        raise HTTPException(status_code=400, detail="image_urls must not be empty")

    if model_instance is None:
        raise HTTPException(status_code=503, detail="Model not initialised")

    results: list[ImageResult] = []
    failed = 0

    for url in request.image_urls:
        try:
            pil_image = await _fetch_image(url)
            pred = _run_inference(pil_image)
            results.append(ImageResult(url=url, error=None, **pred))
        except httpx.HTTPStatusError as exc:
            logger.warning("HTTP error fetching %s: %s", url, exc)
            results.append(ImageResult(
                url=url, room_type="unknown", condition_score=0.0,
                confidence=0.0, all_class_scores={}, low_confidence=True,
                error=f"HTTP {exc.response.status_code}",
            ))
            failed += 1
        except Exception as exc:
            logger.warning("Error processing %s: %s", url, exc)
            results.append(ImageResult(
                url=url, room_type="unknown", condition_score=0.0,
                confidence=0.0, all_class_scores={}, low_confidence=True,
                error=str(exc),
            ))
            failed += 1

    return AnalyseResponse(
        results=results,
        processed=len(results) - failed,
        failed=failed,
    )
