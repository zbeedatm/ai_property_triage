# Service 2 — Image Analyser

**Stack:** FastAPI · PyTorch · ResNet-50 (transfer learning) · CPU-only

---

## Endpoint

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check + class list |
| POST | `/analyse` | Classify room types + score condition for a list of image URLs |

### POST /analyse

**Request body:**
```json
{
  "image_urls": [
    "https://example.com/kitchen.jpg",
    "https://example.com/living_room.jpg"
  ]
}
```

**Response:**
```json
{
  "results": [
    {
      "url": "https://example.com/kitchen.jpg",
      "room_type": "kitchen",
      "condition_score": 3.8,
      "confidence": 0.82,
      "all_class_scores": {
        "kitchen": 0.82, "living_room": 0.07, "bedroom": 0.03,
        "bathroom": 0.02, "exterior": 0.04, "other": 0.02
      },
      "low_confidence": false,
      "error": null
    }
  ],
  "processed": 1,
  "failed": 0
}
```

**Room type classes:** `kitchen`, `living_room`, `bedroom`, `bathroom`, `exterior`, `other`  
**Condition score:** 1.0 (poor) → 5.0 (excellent)

---

## Setup

### Step 1 — Generate the mock dataset

```bash
python dataset.py --data-dir ./data --images-per-class 40
```

This creates `data/train/`, `data/val/`, `data/test/` with synthetic images.  
**To use real images:** place them in the same folder structure, named `<class>_<id>_cond<1-5>.jpg`.

### Step 2 — Train the model

```bash
pip install -r requirements.txt
python train.py --data-dir ./data --output ./checkpoints/model.pth --epochs 10
```

Target: **≥75% test accuracy**.  
Metrics saved to `checkpoints/metrics.json`.

### Step 3 — Start the service

```bash
docker compose up --build
```

Available at `http://localhost:8002`.

---

## Testing

```bash
# Health check
curl http://localhost:8002/health

# Analyse images
curl -X POST http://localhost:8002/analyse \
  -H "Content-Type: application/json" \
  -d '{
    "image_urls": [
      "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/1200px-Cat03.jpg"
    ]
  }'

# Interactive docs
open http://localhost:8002/docs
```

> **Note:** The service starts even without a trained checkpoint  
> (it logs a warning and uses random weights). Always train first for meaningful results.

---

## Model architecture

```
ResNet-50 backbone (frozen, ImageNet weights)
    └─ FC(2048→512) → ReLU → Dropout(0.3)
           ├─ FC(512→256) → ReLU → Dropout → FC(256→6)    [room type logits]
           └─ FC(512→256) → ReLU → Dropout → FC(256→1) → Sigmoid  [condition 0–1]
```

---

## Replacing mock data with real images

1. Collect ≥30 real labelled images per class (180 total minimum, 300 recommended).
2. Organise into `data/train/<class>/`, `data/val/<class>/`, `data/test/<class>/`.
3. Name files: `<class>_<id>_cond<1-5>.jpg`  (condition score in filename).
4. Re-run `train.py` — no code changes needed.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PATH` | `./checkpoints/model.pth` | Path to trained checkpoint |
| `CONFIDENCE_THRESHOLD` | `0.50` | Min confidence before flagging `low_confidence: true` |

---

## EC2 Deployment

```bash
docker build -t property-image-analyser .
docker run -d \
  -p 8002:8000 \
  -v $(pwd)/checkpoints:/app/checkpoints \
  --name property_image_analyser \
  property-image-analyser
```
