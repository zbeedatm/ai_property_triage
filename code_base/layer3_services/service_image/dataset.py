"""
dataset.py
----------
Mock dataset utilities for the Image Analyser service.

In production, replace the mock generator with real labelled images
organised in the same folder structure:

    data/
      train/
        kitchen/        (≥30 images)
        living_room/    (≥30 images)
        bedroom/        (≥30 images)
        bathroom/       (≥30 images)
        exterior/       (≥30 images)
        other/          (≥30 images)
      val/
        <same structure>
      test/
        <same structure>

Run this script to generate the mock dataset:

    python dataset.py [--data-dir ./data] [--images-per-class 40]
"""

import argparse
import logging
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# 6 room-type classes the model will learn
CLASSES = ["kitchen", "living_room", "bedroom", "bathroom", "exterior", "other"]

# Rough colour palette per class (makes mock images visually distinguishable)
CLASS_COLOURS = {
    "kitchen":     ((200, 230, 200), (100, 180, 100)),
    "living_room": ((230, 210, 190), (160, 120,  80)),
    "bedroom":     ((200, 200, 230), ( 80,  80, 160)),
    "bathroom":    ((190, 220, 230), ( 60, 140, 180)),
    "exterior":    ((180, 220, 180), ( 60, 160,  60)),
    "other":       ((210, 210, 210), (120, 120, 120)),
}

# Condition scores (1–5) are randomly assigned in the mock;
# in production these would come from human labels.
CONDITION_SCORES = [1, 2, 3, 4, 5]


def _make_mock_image(class_name: str, index: int, size: tuple[int, int] = (224, 224)) -> Image.Image:
    """
    Generate a synthetic RGB image for a given room class.
    Uses class-specific colours + random noise so the CNN can learn
    at least a trivial colour-based pattern during mock training.
    """
    bg_colour, accent_colour = CLASS_COLOURS[class_name]

    # Background with slight noise
    arr = np.full((*size, 3), bg_colour, dtype=np.uint8)
    noise = np.random.randint(-20, 20, arr.shape, dtype=np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, mode="RGB")

    # Draw a coloured rectangle as a rough "feature"
    draw = ImageDraw.Draw(img)
    rx1 = random.randint(20, 80)
    ry1 = random.randint(20, 80)
    rx2 = random.randint(140, 200)
    ry2 = random.randint(140, 200)
    draw.rectangle([rx1, ry1, rx2, ry2], fill=accent_colour)

    # Label the image so it's easy to spot during visual inspection
    draw.text((4, 4), f"{class_name} #{index}", fill=(0, 0, 0))

    return img


def generate_mock_dataset(data_dir: str, images_per_class: int = 40) -> None:
    """
    Create the folder hierarchy and populate it with synthetic images.
    Split: 70% train / 15% val / 15% test.
    """
    base = Path(data_dir)
    splits = {
        "train": int(images_per_class * 0.70),
        "val":   int(images_per_class * 0.15),
        "test":  int(images_per_class * 0.15),
    }
    # Ensure totals add up
    splits["train"] += images_per_class - sum(splits.values())

    total = 0
    for split, count in splits.items():
        for cls in CLASSES:
            folder = base / split / cls
            folder.mkdir(parents=True, exist_ok=True)
            for i in range(count):
                condition = random.choice(CONDITION_SCORES)
                img = _make_mock_image(cls, i)
                filename = f"{cls}_{i:04d}_cond{condition}.jpg"
                img.save(folder / filename, format="JPEG", quality=85)
                total += 1

    logger.info(
        "Mock dataset created at '%s' — %d images total (%d classes × %d images, split 70/15/15)",
        data_dir, total, len(CLASSES), images_per_class,
    )
    logger.info("Classes: %s", ", ".join(CLASSES))
    logger.info(
        "To replace with real data: keep the same folder structure and "
        "name files as  <class>_<id>_cond<1-5>.jpg"
    )


# ---------------------------------------------------------------------------
# PyTorch Dataset class
# ---------------------------------------------------------------------------

import torch
from torch.utils.data import Dataset
from torchvision import transforms

# Standard ImageNet normalisation used by ResNet-50
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

TRAIN_TRANSFORMS = transforms.Compose([
    transforms.Resize((256, 256)),
    transforms.RandomCrop(224),
    transforms.RandomHorizontalFlip(),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])

EVAL_TRANSFORMS = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])

CLASS_TO_IDX = {cls: idx for idx, cls in enumerate(CLASSES)}
IDX_TO_CLASS = {idx: cls for cls, idx in CLASS_TO_IDX.items()}


class PropertyImageDataset(Dataset):
    """
    Reads images from:
        <root>/<split>/<class_name>/<filename>.jpg

    Filename convention for condition score:
        <anything>_cond<1-5>.jpg   →  condition score extracted from filename
        If no _cond suffix, condition score defaults to 3 (unknown).
    """

    def __init__(self, root: str, split: str = "train"):
        self.transform = TRAIN_TRANSFORMS if split == "train" else EVAL_TRANSFORMS
        self.samples: list[tuple[Path, int, float]] = []  # (path, class_idx, condition)

        split_dir = Path(root) / split
        if not split_dir.exists():
            raise FileNotFoundError(f"Split directory not found: {split_dir}")

        for cls in CLASSES:
            cls_dir = split_dir / cls
            if not cls_dir.exists():
                continue
            for img_path in sorted(cls_dir.glob("*.jpg")):
                condition = self._parse_condition(img_path.stem)
                self.samples.append((img_path, CLASS_TO_IDX[cls], condition))

        if not self.samples:
            raise RuntimeError(f"No images found under {split_dir}")

        logger.info("PropertyImageDataset [%s]: %d images", split, len(self.samples))

    @staticmethod
    def _parse_condition(stem: str) -> float:
        """Extract condition score from filename stem, e.g. 'kitchen_0001_cond4' → 4.0."""
        if "_cond" in stem:
            try:
                return float(stem.split("_cond")[-1])
            except ValueError:
                pass
        return 3.0  # default: unknown condition

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        path, class_idx, condition = self.samples[idx]
        img = Image.open(path).convert("RGB")
        tensor = self.transform(img)
        return tensor, class_idx, torch.tensor(condition / 5.0, dtype=torch.float32)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate mock property image dataset")
    parser.add_argument("--data-dir", default="./data", help="Output directory")
    parser.add_argument("--images-per-class", type=int, default=40,
                        help="Total images per class (split 70/15/15)")
    args = parser.parse_args()

    random.seed(42)
    np.random.seed(42)
    generate_mock_dataset(args.data_dir, args.images_per_class)
