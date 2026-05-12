"""
model.py
--------
ResNet-50 transfer-learning model with two output heads:

  - Classification head  : 6-class room type (softmax)
  - Regression head      : condition score 0–1 (sigmoid → multiply by 5 at inference)

Architecture:
    ResNet-50 backbone (frozen) → shared feature vector (2048-d)
        ├─ FC(2048→256) → ReLU → Dropout(0.3) → FC(256→6)   [room type]
        └─ FC(2048→256) → ReLU → Dropout(0.3) → FC(256→1)   [condition score]
"""

import torch
import torch.nn as nn
from torchvision import models
from torchvision.models import ResNet50_Weights


class PropertyImageModel(nn.Module):
    def __init__(self, num_classes: int = 6, freeze_backbone: bool = True):
        super().__init__()

        # Load pre-trained ResNet-50
        backbone = models.resnet50(weights=ResNet50_Weights.IMAGENET1K_V2)

        # Freeze all backbone layers
        if freeze_backbone:
            for param in backbone.parameters():
                param.requires_grad = False

        # Remove the original fully-connected head
        # backbone.fc is Linear(2048, 1000) — we replace it
        in_features = backbone.fc.in_features  # 2048
        backbone.fc = nn.Identity()
        self.backbone = backbone

        # Shared intermediate layer (optional; improves both heads)
        self.shared = nn.Sequential(
            nn.Linear(in_features, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
        )

        # --- Classification head ---
        self.classifier = nn.Sequential(
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes),
        )

        # --- Regression head (condition score) ---
        self.regressor = nn.Sequential(
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 1),
            nn.Sigmoid(),   # output in [0, 1]; multiply by 5 at inference
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.backbone(x)         # (B, 2048)
        shared   = self.shared(features)    # (B, 512)
        logits   = self.classifier(shared)  # (B, num_classes)
        score    = self.regressor(shared)   # (B, 1)
        return logits, score.squeeze(1)     # (B, num_classes), (B,)
