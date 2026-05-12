"""
train.py
--------
Transfer-learning training script for the PropertyImageModel.

Usage:
    # 1. Generate mock dataset first:
    python dataset.py --data-dir ./data --images-per-class 40

    # 2. Train:
    python train.py --data-dir ./data --epochs 10 --output ./checkpoints/model.pth

Loss:
    Combined loss = CrossEntropy(room_type) + λ × MSE(condition_score)
    λ (lambda_reg) balances the two heads; default 0.5.

Outputs:
    checkpoints/model.pth    — best checkpoint by validation accuracy
    checkpoints/metrics.json — per-epoch metrics for review
"""

import argparse
import json
import logging
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from dataset import PropertyImageDataset, IDX_TO_CLASS
from model import PropertyImageModel

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

def train_one_epoch(model, loader, optimiser, ce_loss, mse_loss, lambda_reg, device):
    model.train()
    total_loss = correct = total = 0

    for imgs, labels, conditions in loader:
        imgs       = imgs.to(device)
        labels     = labels.to(device)
        conditions = conditions.to(device)

        optimiser.zero_grad()
        logits, scores = model(imgs)

        loss_cls  = ce_loss(logits, labels)
        loss_reg  = mse_loss(scores, conditions)
        loss      = loss_cls + lambda_reg * loss_reg

        loss.backward()
        optimiser.step()

        total_loss += loss.item() * imgs.size(0)
        preds       = logits.argmax(dim=1)
        correct    += (preds == labels).sum().item()
        total      += imgs.size(0)

    return total_loss / total, correct / total


@torch.no_grad()
def evaluate(model, loader, ce_loss, mse_loss, lambda_reg, device):
    model.eval()
    total_loss = correct = total = 0

    for imgs, labels, conditions in loader:
        imgs       = imgs.to(device)
        labels     = labels.to(device)
        conditions = conditions.to(device)

        logits, scores = model(imgs)
        loss_cls  = ce_loss(logits, labels)
        loss_reg  = mse_loss(scores, conditions)
        loss      = loss_cls + lambda_reg * loss_reg

        total_loss += loss.item() * imgs.size(0)
        preds       = logits.argmax(dim=1)
        correct    += (preds == labels).sum().item()
        total      += imgs.size(0)

    return total_loss / total, correct / total


@torch.no_grad()
def test_evaluation(model, loader, device):
    """Detailed per-class accuracy on the test split."""
    model.eval()
    class_correct = {cls: 0 for cls in IDX_TO_CLASS.values()}
    class_total   = {cls: 0 for cls in IDX_TO_CLASS.values()}
    overall_correct = overall_total = 0

    for imgs, labels, _ in loader:
        imgs   = imgs.to(device)
        labels = labels.to(device)

        logits, _ = model(imgs)
        preds = logits.argmax(dim=1)

        for label, pred in zip(labels.cpu(), preds.cpu()):
            cls = IDX_TO_CLASS[label.item()]
            class_total[cls]   += 1
            overall_total      += 1
            if label == pred:
                class_correct[cls] += 1
                overall_correct    += 1

    logger.info("--- Test results ---")
    for cls in IDX_TO_CLASS.values():
        n = class_total[cls]
        acc = class_correct[cls] / n if n else 0
        logger.info("  %-14s  %d/%d  (%.1f%%)", cls, class_correct[cls], n, acc * 100)
    overall = overall_correct / overall_total if overall_total else 0
    logger.info("  Overall: %.1f%%  (target ≥ 75%%)", overall * 100)
    return overall


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Using device: %s", device)

    # Datasets
    train_ds = PropertyImageDataset(args.data_dir, split="train")
    val_ds   = PropertyImageDataset(args.data_dir, split="val")
    test_ds  = PropertyImageDataset(args.data_dir, split="test")

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,  num_workers=0)
    val_loader   = DataLoader(val_ds,   batch_size=args.batch_size, shuffle=False, num_workers=0)
    test_loader  = DataLoader(test_ds,  batch_size=args.batch_size, shuffle=False, num_workers=0)

    # Model
    model = PropertyImageModel(num_classes=6, freeze_backbone=True).to(device)
    logger.info("Model loaded — backbone frozen, training classification + regression heads only")

    # Only train the unfrozen head parameters
    trainable = [p for p in model.parameters() if p.requires_grad]
    logger.info("Trainable parameters: %d", sum(p.numel() for p in trainable))

    optimiser = torch.optim.Adam(trainable, lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.StepLR(optimiser, step_size=5, gamma=0.5)
    ce_loss   = nn.CrossEntropyLoss()
    mse_loss  = nn.MSELoss()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    best_val_acc = 0.0
    all_metrics  = []

    for epoch in range(1, args.epochs + 1):
        tr_loss, tr_acc = train_one_epoch(
            model, train_loader, optimiser, ce_loss, mse_loss, args.lambda_reg, device
        )
        va_loss, va_acc = evaluate(
            model, val_loader, ce_loss, mse_loss, args.lambda_reg, device
        )
        scheduler.step()

        metrics = {
            "epoch":    epoch,
            "train_loss": round(tr_loss, 4),
            "train_acc":  round(tr_acc,  4),
            "val_loss":   round(va_loss, 4),
            "val_acc":    round(va_acc,  4),
        }
        all_metrics.append(metrics)
        logger.info(
            "Epoch %02d/%02d | train loss %.4f acc %.1f%% | val loss %.4f acc %.1f%%",
            epoch, args.epochs, tr_loss, tr_acc * 100, va_loss, va_acc * 100,
        )

        # Save best checkpoint
        if va_acc > best_val_acc:
            best_val_acc = va_acc
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "val_acc": va_acc,
                    "classes": list(IDX_TO_CLASS.values()),
                },
                output_path,
            )
            logger.info("  ✓ Saved best checkpoint (val acc %.1f%%)", va_acc * 100)

    # Save metrics
    metrics_path = output_path.parent / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(all_metrics, f, indent=2)
    logger.info("Metrics saved to %s", metrics_path)

    # Final test evaluation on the best checkpoint
    logger.info("Loading best checkpoint for test evaluation...")
    ckpt = torch.load(output_path, map_location=device)
    model.load_state_dict(ckpt["model_state_dict"])
    test_acc = test_evaluation(model, test_loader, device)

    if test_acc >= 0.75:
        logger.info("✓ Target met: test accuracy %.1f%% ≥ 75%%", test_acc * 100)
    else:
        logger.warning(
            "✗ Target NOT met: test accuracy %.1f%% < 75%%. "
            "Add more real images or unfreeze more backbone layers.",
            test_acc * 100,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train PropertyImageModel")
    parser.add_argument("--data-dir",   default="./data",                   help="Dataset root directory")
    parser.add_argument("--output",     default="./checkpoints/model.pth",  help="Output checkpoint path")
    parser.add_argument("--epochs",     type=int,   default=10)
    parser.add_argument("--batch-size", type=int,   default=16)
    parser.add_argument("--lr",         type=float, default=1e-3)
    parser.add_argument("--lambda-reg", type=float, default=0.5,
                        help="Weight for regression loss (condition score)")
    args = parser.parse_args()
    main(args)
