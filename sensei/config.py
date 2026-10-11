"""All tunables of the pipeline in one dataclass, saved next to every model as ``config.json``.

A model directory stores the ``Config`` it was fitted with, so ``predict`` always extracts the same features
as ``fit``. Fields an older model's config lacks take the value that model was fitted with
(``LEGACY_FEATURE_DEFAULTS``), and unknown fields are ignored with a warning.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# feature settings that older model configs do not mention: they were fitted with these values
LEGACY_FEATURE_DEFAULTS: dict[str, Any] = {"int8_clip": False, "int8_dino": False, "bf16": False}


@dataclass
class Config:
    """Pipeline settings. The defaults are the label-free path; labels only enter through ``calibrate``."""

    backend: str = "deep"            # "deep" (CLIP+DINOv2) | "lite" (handcrafted only, fast, no torch)
    device: str = "auto"             # auto -> cuda if available else cpu
    crop_size: int = 224
    inset: float = 0.06              # shrink each quad towards its centre before warping (avoid neighbours)
    max_images_per_camera: int = 150  # subsample train/test for fit (evenly over time)
    batch_size: int = 32
    clip_model: str = "openai/clip-vit-base-patch16"
    dino_model: str = "facebook/dinov2-small"
    # inference precision of the image encoders (part of the feature-cache key and of the saved model, so
    # predict always matches fit; CLIP text embeddings stay fp32). int8 = dynamic int8 nn.Linear, CPU only.
    int8_clip: bool = False          # tried, not used: CLIP image cosine to fp32 only ~0.75 (quick test, not saved)
    int8_dino: bool = False          # tried, not used: lower late-frame stock score (quick test, not saved)
    # bfloat16 autocast for the image encoders that are not int8 (only where bf16 is native, else fp32). On one
    # core: 3.23 CPU-s per image against 5.16 in fp32 (-37%; outputs/benchmark/cost_1t_bf16.json vs cost_1t.json,
    # tools/benchmark_cost.py). The score check was a quick test without a saved result file.
    bf16: bool = True
    # stock
    n_patch_clusters: int = 24
    pca_dims: int = 48
    level_prior: tuple = (0.15, 0.35, 0.50)  # empty, half, full: stock posterior of an area with no fit-time fill
    # compliance
    compliance_prior: float = 0.93
    # temporal
    smoothing_window_s: int = 300
    smoothing_weight: float = 0.0    # weight of time neighbours vs the frame itself (0 = off)
    seed: int = 0
    extra: dict = field(default_factory=dict)  # free-form knobs for experiments (kept in the JSON)

    def __post_init__(self) -> None:
        if self.backend not in ("deep", "lite"):
            raise ValueError(f"backend must be 'deep' or 'lite', got {self.backend!r}")
        self.level_prior = tuple(float(p) for p in self.level_prior)
        if len(self.level_prior) != 3:
            raise ValueError("level_prior needs 3 values (empty, half, full)")
        if not 0.0 <= self.inset < 1.0:
            raise ValueError("inset must be in [0, 1)")

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["level_prior"] = list(self.level_prior)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Config":
        """Build from a dict, ignoring (and logging) unknown keys so old/new model dirs still load.
        Feature fields missing from an older model's config take the value that model was fitted with
        (``LEGACY_FEATURE_DEFAULTS``), not today's default, so its predict features still match fit."""
        names = {f.name for f in dataclasses.fields(cls)}
        d = {**LEGACY_FEATURE_DEFAULTS, **d}
        unknown = sorted(set(d) - names)
        if unknown:
            log.warning("Config: ignoring unknown keys %s", unknown)
        return cls(**{k: v for k, v in d.items() if k in names})

    def to_json(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: str | Path) -> "Config":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def replace(self, **changes: Any) -> "Config":
        """Copy with some fields changed (validated again)."""
        return dataclasses.replace(self, **changes)

    def resolve_device(self) -> str:
        """'cuda' or 'cpu' for device='auto' (imports torch lazily); otherwise the given device."""
        if self.device != "auto":
            return self.device
        try:
            import torch  # noqa: PLC0415 - optional dependency
        except ImportError:
            return "cpu"
        return "cuda" if torch.cuda.is_available() else "cpu"
